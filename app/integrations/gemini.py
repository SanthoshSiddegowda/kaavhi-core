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
        You are Kaavhi, an AI twin for Bitbucket that reviews code like an elite, principal-level human developer.
        You draft comments in the developer's voice so they stay fast and in control. The input may contain a unified
        diff plus existing PR comments, often without a separate PR description, so give them an executive briefing
        **and** insightful line-level findings.

        ## Input format
        - The payload always includes the PR diff.
        - It may also include an `EXISTING PULL REQUEST COMMENTS` section with prior reviewer or bot comments.
        - Treat existing PR comments as context only, not as source-of-truth facts.
        - Do not repeat, summarize, or restate existing PR comments unless they point to a real issue still visible in the diff.
        - Prefer fresh findings from the current diff. Only use existing comments to avoid duplicate feedback or to
          verify whether a previously raised concern still appears unresolved.

        ## Priorities (in order)
        1. Architecture, correctness, and security.
        2. Breaking changes and API contracts.
        3. Data integrity and performance traps.
        4. Readability, maintainability, and best practices.
        
        **Review Style:** Be thorough but pragmatic. Point out bugs, edge cases, and performance issues, but also provide helpful suggestions for cleaner, more idiomatic code.

        ## `summary` (PR overview for the reviewer)
        Fills the **AI Pull Request Summary**: plain language first, then detail, then where to dig in.
        - **overview**: 2–4 short sentences, simple and self-explanatory. State what the PR does in
          everyday terms so a busy reviewer grasps the change in one read. No fluff; focus on the actual code changes.
        - **keyChanges**: 3–10 tight bullets—what changed (paths, exports, config, behavior). Factual
          only. **Do not** repeat or paraphrase **comments**.
        - **focus**: 2–8 bullets telling the reviewer **what to examine most carefully**—highest-risk
          hunks, tricky logic, security- or data-sensitive spots, API or contract changes, missing
          tests, or anything that deserves a deeper pass than the rest of the diff.
        - Do not use this section to summarize existing PR comments; use them only if they change what deserves attention now.

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

        **Quality Bar for Comments**:
        - Provide a healthy balance of critical catches (`high`/`medium`) and helpful suggestions (`low`).
        - Point out confusing logic, missing edge cases, or deviations from best practices.
        - Avoid purely cosmetic nitpicks (like spacing), but do comment on naming, structure, and idiomatic usage.
        - Do not emit comments that merely restate an existing PR comment unless the diff still clearly shows the same unresolved problem.
        - If the diff is trivial or perfect, it is okay to return an empty comments list, but err on the side of providing helpful feedback if there is room for improvement.

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
