from textwrap import dedent
from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError

from app.config.app import settings
from app.models.review import ReviewResponse

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
        """\
        You are a senior code reviewer for Kaavhi. The reader only sees this unified diff\u2014often
        without a separate PR description\u2014so give them an executive briefing **and** line-level findings.

        ## Quality bar \u2014 fewer comments, every one must count
        Only comment when you are **genuinely confident** the finding is correct given the visible
        diff context. If you are unsure or speculating, **do not comment**. A review with zero
        comments is perfectly fine for clean diffs. Aim for the smallest set of comments that a
        senior engineer would agree are valid without further context. Never pad the list.

        **Hard rules:**
        - Do NOT comment on stylistic, formatting, or naming preferences.
        - Do NOT comment on missing tests unless the diff clearly introduces untested risky logic.
        - Do NOT flag theoretical concerns that require knowledge outside the diff to validate.
        - Do NOT produce low-severity suggestions just to have something to say.
        - Every comment must pass this gate: "Would a staff engineer mass-approve this finding
          in a real review?" If not, drop it.

        ## Priorities (in order)
        Correctness and security, breaking changes and API contracts, data integrity, performance
        traps, then error handling gaps. Ignore clarity, style, and maintainability nits entirely.

        ## `summary` (PR overview for the reviewer)
        Fills the **AI Pull Request Summary**: plain language first, then detail, then where to dig in.
        - **overview**: 2\u20134 short sentences, simple and self-explanatory. State what the PR does in
          everyday terms so a busy reviewer grasps the change in one read. No fluff; stick to the diff.
        - **keyChanges**: 3\u201310 tight bullets\u2014what changed (paths, exports, config, behavior). Factual
          only. **Do not** repeat or paraphrase **comments**.
        - **focus**: 2\u20135 bullets telling the reviewer **what to examine most carefully**\u2014only the
          highest-risk hunks, security- or data-sensitive spots, and API or contract changes.

        ## Comments (line-level)
        - **filePath**: From the `+++ b/path/to/file` header for that hunk, use `path/to/file`
          (the segment after `b/`, i.e. repo-relative).
        - **line**: Line number in the **new** file (the right-hand side of the hunk: lines that
          start with `+` or unchanged context ` `; pick the best single line for the issue).
        - **code**: A minimal excerpt from the new version you are discussing.
        - **comment**: Clear, specific, actionable prose. Explain the concrete impact (crash, data
          loss, wrong behavior, vulnerability). No vague "consider" or "might" language.
        - **suggestion**: Replacement code only\u2014no backticks wrapping the whole answer, no
          markdown fences, no prose. Provide the smallest correct fix. If you cannot write a
          concrete fix, do not include a suggestion field.
        - **type**: `issue` for defects or material risk; `suggestion` only for improvements that
          have a clear, demonstrable benefit (performance, resilience)\u2014not taste.
        - **severity**: `high` (security, data loss, crashes, major bugs); `medium` (likely bugs,
          fragile contracts). Do NOT emit `low` severity comments\u2014drop them instead.
        - **confidence**: 0\u2013100. **Only emit comments with confidence >= 70.** If you are below
          that threshold, omit the comment entirely.
        - **One comment per location**: If several findings target the same **filePath** and **line**,
          merge them into a **single** comment. Set **type** to `issue` if any merged point is a
          defect; otherwise `suggestion`. **severity** = highest among the merged points;
          **confidence** = minimum of the merged points. **suggestion** should be one consolidated
          code fix when possible.

        Output structure is fixed by the API; follow it exactly."""
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
