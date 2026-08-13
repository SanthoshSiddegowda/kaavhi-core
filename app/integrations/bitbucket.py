import asyncio
import logging
import re
from typing import Any, Optional

import httpx

log = logging.getLogger("bitbucket")

_API_BASE = "https://api.bitbucket.org/2.0"
_PAGE_LIMIT = 100
# Bitbucket caps the pull requests endpoint at a page size of 50 (repos allow 100).
_PR_PAGE_LIMIT = 50
_TIMEOUT = httpx.Timeout(15.0)

# Text prepended to each cross-repo PR url appended to a PR title.
_MARKER = "🔗 Cross-repo PR: "

_PR_URL_RE = re.compile(
    r"https?://bitbucket\.org/"
    r"(?P<workspace>[^/]+)/(?P<repo>[^/]+)/pull-requests/(?P<id>\d+)"
)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    token: str,
    params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    resp = await client.get(url, headers=_auth_headers(token), params=params)
    resp.raise_for_status()
    return resp.json()


async def _list_repo_slugs(
    client: httpx.AsyncClient, workspace: str, token: str
) -> list[str]:
    """Return every repository slug in the workspace, following pagination."""
    slugs: list[str] = []
    url: Optional[str] = f"{_API_BASE}/repositories/{workspace}"
    params: Optional[dict[str, Any]] = {
        "pagelen": _PAGE_LIMIT,
        "fields": "values.slug,next",
    }
    while url:
        data = await _get_json(client, url, token, params)
        slugs.extend(repo["slug"] for repo in data.get("values", []) if repo.get("slug"))
        # ``next`` already encodes the query string for the following page.
        url = data.get("next")
        params = None
    return slugs


async def _open_prs_for_branch(
    client: httpx.AsyncClient,
    workspace: str,
    slug: str,
    branch: str,
    token: str,
) -> list[dict[str, str]]:
    """Open PRs in a single repo whose source branch matches ``branch``."""
    url = f"{_API_BASE}/repositories/{workspace}/{slug}/pullrequests"
    params = {
        "q": f'state="OPEN" AND source.branch.name="{branch}"',
        "fields": "values.title,values.links.html.href",
        "pagelen": _PR_PAGE_LIMIT,
    }
    try:
        data = await _get_json(client, url, token, params)
    except httpx.HTTPError as e:
        # A single repo failing (permissions, etc.) must not abort the whole search,
        # but log it so real problems are not silently swallowed.
        log.warning("Cross-repo PR lookup failed for %s: %s", slug, e)
        return []

    matches: list[dict[str, str]] = []
    for pr in data.get("values", []):
        href = pr.get("links", {}).get("html", {}).get("href")
        if href:
            matches.append({"repo": slug, "title": pr.get("title", ""), "url": href})
    return matches


async def _find_cross_repo_prs(
    client: httpx.AsyncClient,
    workspace: str,
    branch: str,
    token: str,
) -> list[dict[str, str]]:
    """
    Find open PRs that share ``branch`` as their source branch across every repo in
    ``workspace``. Returns ``[{"repo", "title", "url"}, ...]`` (possibly empty).

    Raises ``httpx.HTTPError`` only if the workspace repo listing itself fails; per-repo
    lookup failures are swallowed so one inaccessible repo cannot break the result.
    """
    slugs = await _list_repo_slugs(client, workspace, token)
    results = await asyncio.gather(
        *(
            _open_prs_for_branch(client, workspace, slug, branch, token)
            for slug in slugs
        )
    )
    return [pr for repo_prs in results for pr in repo_prs]


def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Parse a Bitbucket PR url into ``(workspace, repo, pr_id)``.

    Raises ``ValueError`` if ``url`` is not a recognizable Bitbucket PR url.
    """
    match = _PR_URL_RE.search(url)
    if not match:
        raise ValueError(f"Not a Bitbucket pull request url: {url!r}")
    return match["workspace"], match["repo"], int(match["id"])


async def _get_pr(
    client: httpx.AsyncClient, workspace: str, repo: str, pr_id: int, token: str
) -> dict[str, Any]:
    url = f"{_API_BASE}/repositories/{workspace}/{repo}/pullrequests/{pr_id}"
    return await _get_json(
        client, url, token, {"fields": "title,source.branch.name"}
    )


async def _update_pr_title(
    client: httpx.AsyncClient,
    workspace: str,
    repo: str,
    pr_id: int,
    title: str,
    token: str,
) -> None:
    url = f"{_API_BASE}/repositories/{workspace}/{repo}/pullrequests/{pr_id}"
    resp = await client.put(url, headers=_auth_headers(token), json={"title": title})
    resp.raise_for_status()


def _build_annotated_title(title: str, cross_repo_prs: list[dict[str, str]]) -> str:
    """Append ``🔗 Cross-repo PR: <url>`` for each cross-repo PR not already in the title."""
    new_title = title
    for pr in cross_repo_prs:
        if pr["url"] not in new_title:
            # rstrip so a trailing space on the title does not produce a double space.
            new_title = f"{new_title.rstrip()} {_MARKER}{pr['url']}"
    return new_title


async def annotate_cross_repo_group(
    pr_url: str, token: str, dry_run: bool = True
) -> dict[str, Any]:
    """
    Cross-link **every** open PR that shares the source branch of ``pr_url`` across the
    workspace. Each PR in the group (the one at ``pr_url`` *and* the matching PRs in other
    repos) has ``🔗 Cross-repo PR: <url>`` appended to its title for every *other* PR in the
    group. Nothing happens when there is only one PR (no cross-repo siblings).

    ``dry_run=True`` (default) previews every change without writing. The operation is
    idempotent—urls already present in a title are not appended again.
    """
    workspace, source_repo, source_id = parse_pr_url(pr_url)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        pr = await _get_pr(client, workspace, source_repo, source_id, token)
        branch = pr.get("source", {}).get("branch", {}).get("name")
        if not branch:
            raise ValueError(f"Could not determine source branch for {pr_url}")

        # The whole group = every open PR with this branch in the workspace, including the
        # one we were given (do not exclude its repo this time).
        members = await _find_cross_repo_prs(client, workspace, branch, token)
        for member in members:
            member["pr_id"] = parse_pr_url(member["url"])[2]

        results: list[dict[str, Any]] = []
        for member in members:
            others = [o for o in members if o["url"] != member["url"]]
            new_title = _build_annotated_title(member["title"], others)
            changed = new_title != member["title"]
            if changed and not dry_run:
                await _update_pr_title(
                    client, workspace, member["repo"], member["pr_id"], new_title, token
                )
            results.append(
                {
                    "repo": member["repo"],
                    "pr_id": member["pr_id"],
                    "url": member["url"],
                    "old_title": member["title"],
                    "new_title": new_title,
                    "changed": changed,
                    "updated": changed and not dry_run,
                }
            )

    return {"workspace": workspace, "branch": branch, "members": results}
