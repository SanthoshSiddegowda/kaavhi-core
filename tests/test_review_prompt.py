from app.integrations.review_prompt import annotate_diff

DIFF = """diff --git a/app/x.py b/app/x.py
--- a/app/x.py
+++ b/app/x.py
@@ -10,4 +10,5 @@ def f():
     ctx
-    old
+    new
+    extra
     tail
"""


def test_annotate_diff_numbers_new_file_lines():
    gutters = [
        line.split("|", 1)[0].strip() for line in annotate_diff(DIFF).splitlines()
    ]
    # headers and the hunk header carry no number; '-' lines are unnumbered;
    # context/'+' lines count up from the hunk's new-file start (10).
    assert gutters == ["", "", "", "", "10", "", "11", "12", "13"]


def test_annotate_diff_restarts_per_hunk():
    diff = DIFF + "@@ -100,2 +200,2 @@\n a\n+b\n"
    lines = annotate_diff(diff).splitlines()
    assert lines[-2].startswith("  200|")
    assert lines[-1].startswith("  201|")


def test_comment_anchor_defaults_to_replace():
    """Older providers omit `anchor`; the response must still validate."""
    from app.models.review import ReviewComment
    c = ReviewComment.model_validate({
        "id": "1", "type": "issue", "severity": "high", "line": 5, "code": "x",
        "comment": "c", "suggestion": "y", "confidence": 90, "filePath": "f",
    })
    assert c.anchor == "replace"


def test_comment_anchor_accepts_inserts():
    from app.models.review import ReviewComment
    for anchor in ("replace", "insert_before", "insert_after"):
        c = ReviewComment.model_validate({
            "id": "1", "type": "issue", "severity": "high", "line": 5, "code": "x",
            "comment": "c", "suggestion": "y", "anchor": anchor,
            "confidence": 90, "filePath": "f",
        })
        assert c.anchor == anchor


def _comment(**over):
    from app.models.review import ReviewComment
    base = {"id": "1", "type": "issue", "severity": "high", "line": 5,
            "code": "    foreach ($rows as $row) {", "comment": "c",
            "suggestion": "", "confidence": 90, "filePath": "f"}
    return ReviewComment.model_validate({**base, **over})


def test_insert_after_strips_repeated_anchor_line():
    c = _comment(anchor="insert_after",
                 suggestion="    foreach ($rows as $row) {\n        $guard = 1;")
    assert c.suggestion == "        $guard = 1;"


def test_insert_before_strips_trailing_anchor_line():
    c = _comment(anchor="insert_before",
                 suggestion="        $guard = 1;\n    foreach ($rows as $row) {")
    assert c.suggestion == "        $guard = 1;"


def test_insert_without_anchor_line_is_untouched():
    c = _comment(anchor="insert_after", suggestion="        $guard = 1;")
    assert c.suggestion == "        $guard = 1;"


def test_replace_suggestion_is_never_stripped():
    """A replace legitimately restates the anchored line."""
    c = _comment(anchor="replace", suggestion="    foreach ($rows as $row) {")
    assert c.suggestion == "    foreach ($rows as $row) {"
