import logging
from typing import Any

from app.config.app import settings
from app.integrations.gemini import review_with_gemini
from app.integrations.nvidia import review_with_nvidia

log = logging.getLogger("review_service")


def _has_content(review: dict[str, Any]) -> bool:
    """A usable review has findings or a real overview (empty overview => treat as failure)."""
    if not isinstance(review, dict):
        return False
    if review.get("comments"):
        return True
    return bool((review.get("summary") or {}).get("overview", "").strip())


async def review_diff(diff: str) -> dict[str, Any]:
    """
    Review a diff. Gemini is the default provider; NVIDIA (qwen) is a fallback used
    only when Gemini fails or returns nothing useful AND an NVIDIA key is configured.
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


# Backwards-compatible alias (older imports / tests referenced this name).
review_diff_with_gemini = review_diff
