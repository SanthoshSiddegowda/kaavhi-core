from typing import Any

from app.integrations.gemini import review_with_gemini


async def review_diff_with_gemini(diff: str) -> dict[str, Any]:
    """Sends the diff to Gemini; returns comments and ``summary`` for the PR overview UI."""
    return await review_with_gemini(diff) 