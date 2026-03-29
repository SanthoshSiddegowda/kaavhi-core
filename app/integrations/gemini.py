from textwrap import dedent
from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError

from app.config.app import settings
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
    instructions = dedent(
        """
        You are a senior code reviewer for Kaavhi. The reader only sees this unified diff—often
        without a separate PR description—so give them an executive briefing **and** line-level findings.

        ## Priorities (in order)
        Correctness and security, breaking changes and API contracts, data integrity, performance
        traps, tests and error handling, then clarity and maintainability. Ignore pure formatting
        unless it hides a real problem.

        ## `summary` (PR overview for the reviewer)
        Fills the **AI Pull Request Summary**: plain language first, then detail, then where to dig in.
        - **overview**: 2–4 short sentences, simple and self-explanatory. State what the PR does in
          everyday terms so a busy reviewer grasps the change in one read. No fluff; stick to the diff.
        - **keyChanges**: 3–10 tight bullets—what changed (paths, exports, config, behavior). Factual
          only. **Do not** repeat or paraphrase **comments**.
        - **focus**: 2–8 bullets telling the reviewer **what to examine most carefully**—highest-risk
          hunks, tricky logic, security- or data-sensitive spots, API or contract changes, missing
          tests, or anything that deserves a deeper pass than the rest of the diff.

        ## Comments (line-level)
        - **filePath**: From the `+++ b/path/to/file` header for that hunk, use `path/to/file`
          (the segment after `b/`, i.e. repo-relative).
        - **line**: Line number in the **new** file (the right-hand side of the hunk: lines that
          start with `+` or unchanged context ` `; pick the best single line for the issue).
        - **code**: A minimal excerpt from the new version you are discussing.
        - **comment**: Clear, specific, actionable prose. Say *why* it matters when non-obvious.
        - **suggestion**: Replacement code only—no backticks wrapping the whole answer, no
          markdown fences, no “consider doing…” prose. If code is not the right fix, give the
          smallest sensible snippet or the corrected line.
        - **type**: `issue` for defects or material risk; `suggestion` for improvements that are not
          strictly wrong.
        - **severity**: `high` (security, data loss, crashes, major bugs); `medium` (likely bugs,
          fragile contracts); `low` (minor clarity, style).
        - **confidence**: 0–100; lower when you are inferring.
        - **One comment per location**: If several findings target the same **filePath** and **line**,
          merge them into a **single** comment. Combine the points in **comment** (concise bullets or
          short paragraphs). Set **type** to `issue` if any merged point is a defect; otherwise
          `suggestion`. **severity** = highest among the merged points; **confidence** = minimum of
          the merged points if they mixed strong and weak evidence. **suggestion** should be one
          consolidated code fix when possible; if not, use the fix for the most severe issue and
          describe the rest only in **comment**.

        Prefer fewer, higher-signal comments over commenting on every hunk. Trivial or cosmetic-only
        diffs may warrant an empty `comments` list.

        Output structure is fixed by the API; follow it exactly.
        """
    ).strip()

    prompt = f"{instructions}\n\n---\n\n## Diff\n\n{diff}\n"

    try:
        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
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
