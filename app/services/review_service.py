from app.integrations.gemini import review_with_gemini

async def review_diff_with_gemini(diff: str) -> str:
    """
    Sends the diff to Gemini 2.5 Pro and returns the review comments as a string.
    """
    return await review_with_gemini(diff) 