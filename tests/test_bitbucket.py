import httpx
import pytest

from app.integrations import bitbucket


def _patch_transport(monkeypatch, handler):
    """Route every httpx.AsyncClient created in bitbucket.py through ``handler``."""
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        kwargs.pop("timeout", None)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(bitbucket.httpx, "AsyncClient", factory)


# --- parse_pr_url -----------------------------------------------------------


def test_parse_pr_url_extracts_parts():
    assert bitbucket.parse_pr_url(
        "https://bitbucket.org/bizom/bizomweb2/pull-requests/29893"
    ) == ("bizom", "bizomweb2", 29893)


def test_parse_pr_url_rejects_non_pr_url():
    with pytest.raises(ValueError):
        bitbucket.parse_pr_url("https://bitbucket.org/bizom/bizomweb2")


# --- _build_annotated_title (idempotency) -----------------------------------


def test_build_annotated_title_appends_and_is_idempotent():
    title = "My change"
    prs = [{"repo": "other", "title": "x", "url": "https://bitbucket.org/w/other/pull-requests/7"}]
    once = bitbucket._build_annotated_title(title, prs)
    assert once == "My change 🔗 Cross-repo PR: https://bitbucket.org/w/other/pull-requests/7"
    # Running again with the url already present must not append a second time.
    assert bitbucket._build_annotated_title(once, prs) == once
    # A trailing space on the title must not produce a double space before the marker.
    assert bitbucket._build_annotated_title("Trailing ", prs) == (
        "Trailing 🔗 Cross-repo PR: https://bitbucket.org/w/other/pull-requests/7"
    )


# --- pagelen regression -----------------------------------------------------


@pytest.mark.asyncio
async def test_open_prs_for_branch_uses_pr_page_limit(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["pagelen"] = request.url.params.get("pagelen")
        return httpx.Response(200, json={"values": []})

    _patch_transport(monkeypatch, handler)
    async with bitbucket.httpx.AsyncClient() as client:
        await bitbucket._open_prs_for_branch(client, "ws", "repo", "br", "tok")

    # Must be 50: the PR endpoint rejects pagelen=100 with "Invalid pagelen".
    assert seen["pagelen"] == str(bitbucket._PR_PAGE_LIMIT) == "50"


# --- annotate_cross_repo_group (bidirectional) ------------------------------


@pytest.mark.asyncio
async def test_annotate_group_cross_links_both_prs(monkeypatch):
    puts: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/pullrequests/29893") and request.method == "GET":
            return httpx.Response(
                200, json={"title": "Web", "source": {"branch": {"name": "feat/x"}}}
            )
        if request.method == "PUT":
            puts[path] = request.read().decode()
            return httpx.Response(200, json={})
        if path.endswith("/repositories/bizom"):
            return httpx.Response(
                200, json={"values": [{"slug": "web"}, {"slug": "api"}]}
            )
        if "/web/pullrequests" in path:
            return httpx.Response(
                200,
                json={"values": [{"title": "Web", "links": {"html": {"href": "https://bitbucket.org/bizom/web/pull-requests/29893"}}}]},
            )
        if "/api/pullrequests" in path:
            return httpx.Response(
                200,
                json={"values": [{"title": "Api", "links": {"html": {"href": "https://bitbucket.org/bizom/api/pull-requests/55"}}}]},
            )
        return httpx.Response(404, json={})

    _patch_transport(monkeypatch, handler)
    res = await bitbucket.annotate_cross_repo_group(
        "https://bitbucket.org/bizom/web/pull-requests/29893", "tok", dry_run=False
    )

    # Both PRs updated, each pointing at the OTHER.
    assert {m["repo"]: m["updated"] for m in res["members"]} == {"web": True, "api": True}
    assert "/api/pull-requests/55" in puts["/2.0/repositories/bizom/web/pullrequests/29893"]
    assert "/web/pull-requests/29893" in puts["/2.0/repositories/bizom/api/pullrequests/55"]
