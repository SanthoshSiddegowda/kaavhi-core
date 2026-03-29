from typing import List, Literal

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    diff: str


class ReviewComment(BaseModel):
    id: str
    type: Literal["issue", "suggestion"]
    severity: Literal["high", "medium", "low"]
    line: int
    code: str
    comment: str
    suggestion: str = Field(
        ...,
        description="Replacement code only; no prose or markdown fences.",
    )
    confidence: int = Field(..., ge=0, le=100)
    filePath: str


class PullRequestSummary(BaseModel):
    """
    AI Pull Request Summary for reviewers — ``overview`` + ``keyChanges`` + ``focus``.
    Frontend typically maps this to ``reviewResponse.summary``.
    """

    overview: str = Field(
        ...,
        description=(
            "Plain, simple English: in a few short sentences, what this PR changes and why a "
            "reviewer should care—no jargon unless the diff requires it. Easy to skim."
        ),
    )
    keyChanges: List[str] = Field(
        ...,
        description=(
            "Short factual bullets: what files or areas changed and what happened there. "
            "Not line-level review; do not copy text from comments."
        ),
    )
    focus: List[str] = Field(
        ...,
        description=(
            "Where the reviewer should spend extra time: specific files, behaviors, or risk areas "
            "worth a deeper pass (e.g. security-sensitive paths, API contracts, new logic)."
        ),
    )


class ReviewResponse(BaseModel):
    comments: List[ReviewComment]
    summary: PullRequestSummary = Field(
        ...,
        description="Simple PR overview, change list, and review focus for the reviewer.",
    )
