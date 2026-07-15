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
    Review a diff. NVIDIA (qwen) is primary; Gemini is the fallback used when NVIDIA
    is unconfigured, errors (rate limit / no credits / timeout), or returns nothing useful.
    """
    if settings.NVIDIA_API_KEY:
        try:
            review = await review_with_nvidia(diff)
            if _has_content(review):
                return review
            log.warning("NVIDIA returned empty review; falling back to Gemini")
        except Exception as e:  # noqa: BLE001 — any provider failure should fall back
            log.warning("NVIDIA review failed (%s); falling back to Gemini", e)

    return await review_with_gemini(diff)


# Backwards-compatible alias (older imports / tests referenced this name).
review_diff_with_gemini = review_diff
