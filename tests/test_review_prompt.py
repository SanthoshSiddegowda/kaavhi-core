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
