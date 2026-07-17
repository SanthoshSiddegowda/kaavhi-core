from typing import List

from pydantic import BaseModel, Field


class CandidateCommit(BaseModel):
    """A commit that previously touched a file the fix changed (file-level history)."""

    hash: str
    author: str = ""
    date: str = ""
    message: str = ""
    files: List[str] = Field(default_factory=list)


class DetectOriginRequest(BaseModel):
    bug_summary: str = ""
    fix_ref: str = ""  # fix PR URL or commit hash (context only)
    fix_diff: str = ""  # unified diff of the fix
    candidate_commits: List[CandidateCommit] = Field(default_factory=list)


class DetectOriginResponse(BaseModel):
    introduced_commit: str = Field(
        "",
        description="Hash of the candidate commit that most likely introduced the regression. Empty if none is plausible.",
    )
    introduced_by: str = Field(
        "",
        description="Author (name or email) of the introducing commit. Empty if unknown.",
    )
    confidence: int = Field(0, ge=0, le=100, description="0-100; low when guessing or signal is weak.")
    reasoning: str = Field("", description="One or two sentences explaining the choice.")
