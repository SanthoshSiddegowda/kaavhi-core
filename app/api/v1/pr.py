from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.integrations.bitbucket import annotate_cross_repo_group

router = APIRouter(prefix="/pr", tags=["pr"])


class CrossRepoRequest(BaseModel):
    pr_url: str = Field(
        ..., description="Bitbucket pull request url from the reporting table row."
    )
    bitbucket_token: str = Field(
        ...,
        description="Bitbucket access token (e.g. the Supabase `provider_token`).",
    )
    dry_run: bool = Field(
        False,
        description="When true, preview the title changes without writing to Bitbucket.",
    )


@router.post("/cross-repo", status_code=status.HTTP_200_OK)
async def annotate_cross_repo(payload: CrossRepoRequest) -> dict[str, Any]:
    """
    Cross-link every open PR that shares the source branch of ``pr_url`` across the workspace.

    Appends ``🔗 Cross-repo PR: <url>`` to each PR's title for every other PR in the group.
    Returns the group members with their ``old_title``/``new_title`` and whether each was
    updated. Idempotent. Set ``dry_run=true`` to preview without writing.
    """
    try:
        return await annotate_cross_repo_group(
            payload.pr_url, payload.bitbucket_token, dry_run=payload.dry_run
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except httpx.HTTPStatusError as e:
        # Surface Bitbucket auth/permission errors rather than a generic 500.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Bitbucket API error ({e.response.status_code}).",
        ) from e
