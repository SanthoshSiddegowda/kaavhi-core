import httpx
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app

client = TestClient(app)


@pytest.mark.asyncio
@patch("app.api.v1.pr.annotate_cross_repo_group", new_callable=AsyncMock)
async def test_cross_repo_endpoint_returns_group(mock_annotate):
    mock_annotate.return_value = {
        "workspace": "bizom",
        "branch": "feature/x",
        "members": [
            {"repo": "web", "pr_id": 1, "updated": True},
            {"repo": "api", "pr_id": 2, "updated": True},
        ],
    }

    response = client.post(
        "/pr/cross-repo",
        json={
            "pr_url": "https://bitbucket.org/bizom/web/pull-requests/1",
            "bitbucket_token": "tok",
            "dry_run": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["branch"] == "feature/x"
    assert len(response.json()["members"]) == 2
    mock_annotate.assert_awaited_once_with(
        "https://bitbucket.org/bizom/web/pull-requests/1", "tok", dry_run=False
    )


@pytest.mark.asyncio
@patch("app.api.v1.pr.annotate_cross_repo_group", new_callable=AsyncMock)
async def test_cross_repo_endpoint_rejects_bad_url(mock_annotate):
    mock_annotate.side_effect = ValueError("Not a Bitbucket pull request url")

    response = client.post(
        "/pr/cross-repo",
        json={"pr_url": "nope", "bitbucket_token": "tok"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
@patch("app.api.v1.pr.annotate_cross_repo_group", new_callable=AsyncMock)
async def test_cross_repo_endpoint_surfaces_bitbucket_error(mock_annotate):
    request = httpx.Request("GET", "https://api.bitbucket.org/")
    mock_annotate.side_effect = httpx.HTTPStatusError(
        "forbidden", request=request, response=httpx.Response(403, request=request)
    )

    response = client.post(
        "/pr/cross-repo",
        json={"pr_url": "https://bitbucket.org/bizom/web/pull-requests/1", "bitbucket_token": "tok"},
    )

    assert response.status_code == 502
