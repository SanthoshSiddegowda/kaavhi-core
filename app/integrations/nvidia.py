import json
import uuid
from typing import Any

from openai import AsyncOpenAI

from app.config.app import settings
from app.integrations.review_prompt import INSTRUCTIONS, JSON_CONTRACT, build_diff_prompt
from app.models.review import ReviewResponse

# NVIDIA's inference API is OpenAI-compatible.
_client = AsyncOpenAI(
    base_url=settings.NVIDIA_BASE_URL,
    api_key=settings.NVIDIA_API_KEY or "missing",
)

_SYSTEM = f"{INSTRUCTIONS}\n\n{JSON_CONTRACT}"


def _ensure_ids(review: dict[str, Any]) -> dict[str, Any]:
    """qwen may omit/duplicate comment ids; ReviewResponse requires a unique str id."""
    for c in review.get("comments", []) or []:
        if not c.get("id"):
            c["id"] = f"nv-{uuid.uuid4()}"
    return review


async def review_with_nvidia(diff: str) -> dict[str, Any]:
    """
    Review the diff via NVIDIA (qwen). Returns a dict matching ``ReviewResponse``.
    Raises on any error (network, rate limit, empty credits, invalid JSON) so the
    caller can fall back to another provider.
    """
    if not settings.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY not configured")

    response = await _client.chat.completions.create(
        model=settings.NVIDIA_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": build_diff_prompt(diff)},
        ],
        temperature=0.2,  # low → consistent review, fewer hallucinated findings
        max_tokens=8192,
        response_format={"type": "json_object"},
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise ValueError("NVIDIA returned empty content")

    # Validate against the same schema Gemini uses; raises if malformed.
    review = _ensure_ids(json.loads(content))
    return ReviewResponse.model_validate(review).model_dump()
