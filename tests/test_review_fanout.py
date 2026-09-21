from unittest.mock import AsyncMock, patch

import pytest

from app.integrations.review_prompt import split_by_file
from app.services.review_service import _merge, review_diff

GIT_DIFF = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
-x = 1
+x = 2
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -5,2 +5,2 @@
-y = 1
+y = 2
"""

BARE_DIFF = """--- a/a.py
+++ b/a.py
@@ -1,2 +1,2 @@
-x = 1
+x = 2
--- a/b.py
+++ b/b.py
@@ -5,2 +5,2 @@
-y = 1
+y = 2
"""


def test_split_git_format():
    chunks = split_by_file(GIT_DIFF)
    assert len(chunks) == 2
    assert chunks[0].startswith("diff --git a/a.py")
    assert "b.py" not in chunks[0]


def test_split_bare_format():
    chunks = split_by_file(BARE_DIFF)
    assert len(chunks) == 2
    assert "a.py" in chunks[0] and "b.py" not in chunks[0]


def test_single_file_diff_is_not_split():
    one = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x\n+y\n"
    assert split_by_file(one) == [one]


def test_removed_dashes_line_is_not_a_file_boundary():
    """A deleted line starting with '--- ' must not split the diff."""
    tricky = (
        "--- a/a.py\n+++ b/a.py\n@@ -1,3 +1,2 @@\n"
        "--- not a header, just deleted text\n+kept\n"
    )
    assert split_by_file(tricky) == [tricky]


def _review(severity, confidence, cid="1"):
    return {
        "comments": [{
            "id": cid, "type": "issue", "severity": severity, "line": 1, "code": "x",
            "comment": "c", "suggestion": "", "confidence": confidence, "filePath": "f",
        }],
        "summary": {"overview": "o", "keyChanges": ["k"], "focus": ["f"]},
    }


def test_merge_reids_and_orders_by_severity():
    merged = _merge([_review("low", 50), _review("high", 60), _review("medium", 90)])
    assert [c["severity"] for c in merged["comments"]] == ["high", "medium", "low"]
    # Every chunk returned id "1"; merged ids must be unique.
    assert [c["id"] for c in merged["comments"]] == ["1", "2", "3"]
    assert merged["summary"]["keyChanges"] == ["k", "k", "k"]


def test_merge_caps_total_comments():
    with patch("app.services.review_service.MAX_COMMENTS", 2):
        merged = _merge([_review("high", 90), _review("high", 80), _review("high", 70)])
    assert len(merged["comments"]) == 2


@pytest.mark.asyncio
async def test_review_diff_fans_out_per_file():
    with patch("app.services.review_service._review_chunk", new_callable=AsyncMock) as chunk, \
         patch("app.services.review_service.summarize_key_changes",
               new_callable=AsyncMock) as summarize:
        chunk.return_value = _review("high", 90)
        summarize.return_value = "combined overview"
        result = await review_diff(GIT_DIFF)

    assert chunk.await_count == 2, "one model call per file"
    assert result["summary"]["overview"] == "combined overview"
    assert len(result["comments"]) == 2


@pytest.mark.asyncio
async def test_one_failing_file_does_not_lose_the_others():
    with patch("app.services.review_service._review_chunk", new_callable=AsyncMock) as chunk, \
         patch("app.services.review_service.summarize_key_changes",
               new_callable=AsyncMock) as summarize:
        chunk.side_effect = [RuntimeError("boom"), _review("high", 90)]
        summarize.return_value = "overview"
        result = await review_diff(GIT_DIFF)

    assert len(result["comments"]) == 1


@pytest.mark.asyncio
async def test_all_files_failing_returns_empty_schema_valid_review():
    with patch("app.services.review_service._review_chunk", new_callable=AsyncMock) as chunk:
        chunk.side_effect = [RuntimeError("boom"), RuntimeError("boom")]
        result = await review_diff(GIT_DIFF)

    assert result == {"comments": [],
                      "summary": {"overview": "", "keyChanges": [], "focus": []}}


def _c(severity, confidence=80, anchor="replace"):
    return {
        "id": "1", "type": "issue", "severity": severity, "line": 1, "code": "x",
        "comment": "c", "suggestion": "y", "anchor": anchor,
        "confidence": confidence, "filePath": "f",
    }


def test_low_comments_are_budgeted():
    """Per-file reviews each emit a style note; only a few may survive the merge."""
    reviews = [{"comments": [_c("low", 90)], "summary": {}} for _ in range(8)]
    merged = _merge(reviews, file_count=8)
    assert len(merged["comments"]) == 3


def test_low_comments_dropped_on_large_prs():
    reviews = [{"comments": [_c("low", 90)], "summary": {}} for _ in range(12)]
    merged = _merge(reviews, file_count=12)
    assert merged["comments"] == []


def test_low_budget_never_displaces_real_findings():
    reviews = ([{"comments": [_c("low", 99)], "summary": {}} for _ in range(8)]
               + [{"comments": [_c("high", 50)], "summary": {}}])
    merged = _merge(reviews, file_count=9)
    severities = [c["severity"] for c in merged["comments"]]
    assert severities.count("high") == 1, "a high finding must survive a flood of low ones"
    assert severities.count("low") == 3
