from textwrap import dedent

from app.models.detect_origin import DetectOriginRequest

# Shared instructions for regression-origin detection (SZZ-style, heuristic).
INSTRUCTIONS = dedent(
    """
    You are a regression-origin detector. Given a bug, the diff of the commit/PR that FIXED it,
    and a list of candidate commits that previously touched the same files, identify which
    candidate most likely INTRODUCED the regression the fix addresses.

    Reasoning approach (approximate git-blame / SZZ):
    - The fix diff shows which files/lines had to change to correct the bug.
    - The regression was most likely introduced by the most recent prior commit that touched
      those same areas — especially one whose message/timing lines up with the buggy behavior.
    - Prefer commits that changed the same files the fix touched, closest in time before the fix.

    Rules:
    - Choose `introduced_commit` ONLY from the provided candidate hashes. Never invent a hash.
    - If no candidate is plausible (or no candidates given), return empty strings and confidence 0.
    - `introduced_by` must be the author of the chosen candidate.
    - `confidence`: high (70-100) only when a candidate clearly matches the fixed files; medium
      (30-69) when reasonable but uncertain; low (1-29) for weak guesses; 0 when unknown.
    - `reasoning`: one or two sentences, concrete (name the file/overlap), no fluff.
    - `cause_summary`: how the regression was INTRODUCED — the root cause in plain language,
      inferred from the introducing commit + what the fix had to change. 1-3 sentences.
    - `fix_summary`: how the fix RESOLVES it, read from the fix diff. 1-3 sentences. Be concrete
      (e.g. "adds an is_object guard before casting to array"). Leave empty only if truly unclear.

    Output structure is fixed by the API; follow it exactly.
    """
).strip()

# For providers without native schema binding (NVIDIA/OpenAI-compatible).
JSON_CONTRACT = dedent(
    """
    ## Output — return ONLY this JSON object, no markdown:
    {
      "introduced_commit": "string (a candidate hash, or empty)",
      "introduced_by": "string (author, or empty)",
      "confidence": integer 0-100,
      "reasoning": "string",
      "cause_summary": "string (how it was introduced)",
      "fix_summary": "string (how it was fixed)"
    }
    """
).strip()


def build_context(req: DetectOriginRequest, max_diff_chars: int = 6000) -> str:
    diff = (req.fix_diff or "").strip()
    if len(diff) > max_diff_chars:
        diff = diff[:max_diff_chars] + "\n… (diff truncated)"

    candidates = "\n".join(
        f"- {c.hash} | {c.author} | {c.date} | {c.message.splitlines()[0] if c.message else ''} "
        f"| files: {', '.join(c.files[:6])}"
        for c in req.candidate_commits
    ) or "(none)"

    return dedent(
        f"""
        ## Bug
        {req.bug_summary or "(no summary)"}

        ## Fix reference
        {req.fix_ref or "(unknown)"}

        ## Fix diff
        {diff or "(no diff available)"}

        ## Candidate commits (prior history of the changed files)
        {candidates}
        """
    ).strip()
