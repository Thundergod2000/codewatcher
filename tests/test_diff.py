"""Tests for the diff parser."""

from codewatch.diff import parse_diff

SAMPLE_DIFF = """\
diff --git a/codewatch/scanner.py b/codewatch/scanner.py
index abc123..def456 100644
--- a/codewatch/scanner.py
+++ b/codewatch/scanner.py
@@ -1,2 +1,5 @@
+def new_function():
+    pass
+
 def existing():
     pass
diff --git a/README.md b/README.md
index 111..222 100644
--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
+# New heading
"""


def test_only_python_files_returned():
    result = parse_diff(SAMPLE_DIFF)
    assert "README.md" not in result
    assert "codewatch/scanner.py" in result


def test_added_lines_extracted():
    result = parse_diff(SAMPLE_DIFF)
    lines = result["codewatch/scanner.py"]
    assert "def new_function():" in lines
    assert "    pass" in lines


def test_empty_diff_returns_empty():
    result = parse_diff("")
    assert result == {}


def test_added_file_linenos_maps_to_disk(tmp_path, monkeypatch):
    from codewatch.diff import added_file_linenos

    src = tmp_path / "mod.py"
    src.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert added_file_linenos("mod.py", ["c = 3"]) == [3]


def test_binary_file_skipped():
    diff = """\
diff --git a/image.png b/image.png
Binary files a/image.png and b/image.png differ
"""
    result = parse_diff(diff)
    assert result == {}
