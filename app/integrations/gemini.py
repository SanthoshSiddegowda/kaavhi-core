from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError

from app.config.app import settings
from app.integrations.review_prompt import INSTRUCTIONS, build_diff_prompt
from app.models.review import ReviewResponse

# The client is initialized here using the key from the centralized settings.
# Pydantic automatically validates that the key exists.
client = genai.Client(api_key=settings.GEMINI_API_KEY)

_EMPTY_SUMMARY: dict[str, Any] = {"overview": "", "keyChanges": [], "focus": []}


def _response_to_review_dict(response: Any) -> dict[str, Any]:
    """Normalize generate_content response into a plain dict for the review API."""
    try:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, ReviewResponse):
            return parsed.model_dump()
        if isinstance(parsed, dict):
            return ReviewResponse.model_validate(parsed).model_dump()

        text = (response.text or "").strip()
        if not text:
            return {"comments": [], "summary": _EMPTY_SUMMARY}
        return ReviewResponse.model_validate_json(text).model_dump()
    except ValidationError:
        return {"comments": [], "summary": _EMPTY_SUMMARY}


async def review_with_gemini(diff: str) -> dict[str, Any]:
    """
    Reviews the diff with Gemini and returns a dict matching ``ReviewResponse``
    (line comments plus ``summary`` for the AI Pull Request overview; shape from ``response_schema``).
    """
    prompt = f"{INSTRUCTIONS}\n\n---\n\n{build_diff_prompt(diff)}"

    try:
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ReviewResponse,
            ),
        )
        return _response_to_review_dict(response)
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        return {"comments": [], "summary": _EMPTY_SUMMARY}


_SUMMARY_PROMPT = (
    "Below are the key changes from each file of one pull request, reviewed separately.\n"
    "Write the PR overview: 2-4 short sentences, plain everyday language, describing what "
    "the pull request does as a whole. No bullet points, no preamble, no restating the list."
)


async def summarize_key_changes(key_changes: list[str]) -> str:
    """
    Write one overview across per-file reviews.

    Each file is reviewed in its own call, so no single call sees the whole PR. This is a
    small extra request purely to produce the cross-file ``summary.overview``.
    """
    if not key_changes:
        return ""

    bullets = "\n".join(f"- {c}" for c in key_changes)
    try:
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=f"{_SUMMARY_PROMPT}\n\n{bullets}",
        )
        return (response.text or "").strip()
    except Exception as e:  # noqa: BLE001 — an overview is not worth failing the review
        print(f"Error summarizing key changes: {e}")
        # Falling back to the raw list is worse than nothing for a prose field.
        return ""
