import asyncio
import logging
from typing import Any

from app.config.app import settings
from app.integrations.gemini import review_with_gemini, summarize_key_changes
from app.integrations.nvidia import review_with_nvidia
from app.integrations.review_prompt import split_by_file

log = logging.getLogger("review_service")

# Cap on the merged review. Each per-file call is already capped by the prompt; without a
# total cap a 20-file PR could return 300 comments.
MAX_COMMENTS = 15

# Per-file review reintroduces low-severity noise the single-prompt version suppressed: each
# file gets its own reviewer, and each one wants to say something. Budget `low` separately so
# style observations on files nobody cares about cannot crowd out real defects.
MAX_LOW_COMMENTS = 3
# Above this many files, drop `low` entirely — a large PR needs signal, not style notes.
LOW_COMMENT_FILE_LIMIT = 10

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}

_EMPTY: dict[str, Any] = {
    "comments": [],
    "summary": {"overview": "", "keyChanges": [], "focus": []},
}


def _has_content(review: dict[str, Any]) -> bool:
    """A usable review has findings or a real overview (empty overview => treat as failure)."""
    if not isinstance(review, dict):
        return False
    if review.get("comments"):
        return True
    return bool((review.get("summary") or {}).get("overview", "").strip())


async def _review_chunk(diff: str) -> dict[str, Any]:
    """
    Review one diff (a single file, or a whole PR when it cannot be split). Gemini is the
    default provider; NVIDIA (qwen) is a fallback used only when Gemini fails or returns
    nothing useful AND an NVIDIA key is configured.
    """
    try:
        review = await review_with_gemini(diff)
        if _has_content(review):
            return review
        log.warning("Gemini returned empty review")
    except Exception as e:  # noqa: BLE001 — any provider failure should fall back
        log.warning("Gemini review failed (%s)", e)

    if settings.NVIDIA_API_KEY:
        log.warning("Falling back to NVIDIA")
        try:
            return await review_with_nvidia(diff)
        except Exception as e:  # noqa: BLE001
            log.warning("NVIDIA fallback failed (%s)", e)

    # Both unavailable — return an empty, schema-valid review.
    return {"comments": [], "summary": {"overview": "", "keyChanges": [], "focus": []}}


def _merge(reviews: list[dict[str, Any]], file_count: int = 1) -> dict[str, Any]:
    """
    Combine per-file reviews into one response.

    Comment ids are rewritten: each file is reviewed independently, so several chunks
    happily return an id of "1" and the frontend needs them unique. ``low`` comments are
    budgeted separately so per-file style notes cannot crowd out real defects.
    """
    comments, key_changes, focus = [], [], []
    for review in reviews:
        comments += review.get("comments") or []
        summary = review.get("summary") or {}
        key_changes += summary.get("keyChanges") or []
        focus += summary.get("focus") or []

    comments.sort(
        key=lambda c: (_SEVERITY_RANK.get(c.get("severity"), 3), -c.get("confidence", 0))
    )

    low_budget = 0 if file_count > LOW_COMMENT_FILE_LIMIT else MAX_LOW_COMMENTS
    kept: list[dict[str, Any]] = []
    for comment in comments:
        if comment.get("severity") == "low":
            if low_budget == 0:
                continue
            low_budget -= 1
        kept.append(comment)
        if len(kept) == MAX_COMMENTS:
            break

    for i, comment in enumerate(kept, start=1):
        comment["id"] = str(i)

    return {
        "comments": kept,
        "summary": {"overview": "", "keyChanges": key_changes, "focus": focus},
    }


async def review_diff(diff: str) -> dict[str, Any]:
    """
    Review a diff, one model call per file, in parallel.

    Single-file diffs take the same path as before. Multi-file diffs are split so each
    file is reviewed against its own prompt, then merged — reviewing a large PR in one
    prompt measurably loses findings.
    """
    chunks = split_by_file(diff)
    if len(chunks) < 2:
        return await _review_chunk(diff)

    results = await asyncio.gather(
        *(_review_chunk(chunk) for chunk in chunks), return_exceptions=True
    )

    reviews: list[dict[str, Any]] = []
    for chunk_result in results:
        if isinstance(chunk_result, BaseException):
            # One file failing must not lose the other files' findings.
            log.warning("Chunk review failed (%s)", chunk_result)
            continue
        reviews.append(chunk_result)

    if not any(_has_content(r) for r in reviews):
        return dict(_EMPTY, summary=dict(_EMPTY["summary"]))

    merged = _merge(reviews, file_count=len(chunks))
    merged["summary"]["overview"] = await summarize_key_changes(
        merged["summary"]["keyChanges"]
    )
    return merged


# Backwards-compatible alias (older imports / tests referenced this name).
review_diff_with_gemini = review_diff
