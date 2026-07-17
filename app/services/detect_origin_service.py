import logging
from typing import Any

from app.config.app import settings
from app.integrations.detect_origin import detect_with_gemini, detect_with_nvidia
from app.models.detect_origin import DetectOriginRequest

log = logging.getLogger("detect_origin_service")

_EMPTY: dict[str, Any] = {
    "introduced_commit": "",
    "introduced_by": "",
    "confidence": 0,
    "reasoning": "Detection unavailable.",
}


async def detect_origin(req: DetectOriginRequest) -> dict[str, Any]:
    """Gemini default; NVIDIA fallback. Never raises — returns an empty result instead."""
    try:
        return await detect_with_gemini(req)
    except Exception as e:  # noqa: BLE001
        log.warning("Gemini detect-origin failed (%s)", e)

    if settings.NVIDIA_API_KEY:
        try:
            return await detect_with_nvidia(req)
        except Exception as e:  # noqa: BLE001
            log.warning("NVIDIA detect-origin fallback failed (%s)", e)

    return dict(_EMPTY)
