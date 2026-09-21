from typing import List, Literal

from pydantic import BaseModel, Field, model_validator


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
    anchor: Literal["replace", "insert_before", "insert_after"] = Field(
        "replace",
        description=(
            "How ``suggestion`` applies to ``line``. Bitbucket suggestion blocks replace the "
            "lines they are anchored to, so an insert-shaped fix emitted as ``replace`` "
            "silently deletes the anchored line. Defaults to ``replace``."
        ),
    )
    confidence: int = Field(..., ge=0, le=100)
    filePath: str

    @model_validator(mode="after")
    def _drop_anchor_line_from_inserts(self) -> "ReviewComment":
        """
        Strip the anchored line when an insert repeats it.

        The prompt tells the model an insert must carry only new lines, but it still leads
        with the anchored line often enough to matter, and applying that duplicates the line.
        Cheaper to normalize here than to trust the instruction: this runs for every provider.
        """
        if self.anchor == "replace" or not self.suggestion.strip():
            return self

        anchor_line = self.code.strip()
        if not anchor_line:
            return self

        lines = self.suggestion.split("\n")
        if self.anchor == "insert_after" and lines[0].strip() == anchor_line:
            self.suggestion = "\n".join(lines[1:]).rstrip()
        elif self.anchor == "insert_before" and lines[-1].strip() == anchor_line:
            self.suggestion = "\n".join(lines[:-1]).rstrip()
        return self


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
