"""Tests for JS/TS diff parsing."""

from codewatch.diff import parse_diff

JS_DIFF = """\
diff --git a/src/app.js b/src/app.js
index abc123..def456 100644
--- a/src/app.js
+++ b/src/app.js
@@ -1,2 +1,5 @@
+function newFunction() {
+    return 42;
+}
 
 function existing() {
     return 1;
 }
diff --git a/README.md b/README.md
index 111..222 100644
--- a/README.md
+++ b/README.md
@@ -1 +1,2 @@
+# New heading
"""

TSX_DIFF = """\
diff --git a/components/Button.tsx b/components/Button.tsx
index abc123..def456 100644
--- a/components/Button.tsx
+++ b/components/Button.tsx
@@ -1,0 +1,2 @@
+export const Button = () => <button>Click</button>;
+
"""

MIXED_DIFF = """\
diff --git a/codewatch/scanner.py b/codewatch/scanner.py
index abc123..def456 100644
--- a/codewatch/scanner.py
+++ b/codewatch/scanner.py
@@ -1,2 +1,5 @@
+def new_python_function():
+    pass
+
 def existing():
     pass
diff --git a/src/utils.ts b/src/utils.ts
index 111..222 100644
--- a/src/utils.ts
+++ b/src/utils.ts
@@ -1,0 +1,2 @@
+export const helper = () => 1;
+
"""


def test_js_files_included():
    result = parse_diff(JS_DIFF)
    assert "README.md" not in result
    assert "src/app.js" in result


def test_jsx_files_included():
    result = parse_diff(JS_DIFF.replace(".js", ".jsx"))
    assert "src/app.jsx" in result


def test_ts_files_included():
    result = parse_diff(JS_DIFF.replace(".js", ".ts"))
    assert "src/app.ts" in result


def test_tsx_files_included():
    result = parse_diff(TSX_DIFF)
    assert "components/Button.tsx" in result


def test_unrelated_extensions_excluded():
    result = parse_diff(JS_DIFF)
    assert "README.md" not in result


def test_added_lines_extracted_js():
    result = parse_diff(JS_DIFF)
    lines = result["src/app.js"]
    assert "function newFunction() {" in lines
    assert "    return 42;" in lines


def test_mixed_python_js_diff():
    result = parse_diff(MIXED_DIFF)
    assert "codewatch/scanner.py" in result
    assert "src/utils.ts" in result
    assert len(result["codewatch/scanner.py"]) == 3
    assert len(result["src/utils.ts"]) == 2


def test_binary_file_skipped():
    diff = """\
diff --git a/image.png b/image.png
Binary files a/image.png and b/image.png differ
"""
    result = parse_diff(diff)
    assert result == {}


def test_deleted_file_skipped():
    diff = """\
diff --git a/old.js b/old.js
deleted file mode 100644
--- a/old.js
+++ /dev/null
@@ -1 +0,0 @@
-function deleted() {}
"""
    result = parse_diff(diff)
    assert result == {}


def test_renamed_file_with_changes_uses_new_path():
    diff = """\
diff --git a/src/old.js b/src/new.js
similarity index 80%
rename from src/old.js
rename to src/new.js
--- a/src/old.js
+++ b/src/new.js
@@ -1,0 +1,1 @@
+const renamed = true;
"""
    result = parse_diff(diff)
    assert "src/new.js" in result
    assert "src/old.js" not in result


def test_repeated_added_lines_get_exact_line_numbers():
    from codewatch.diff import added_file_linenos

    diff = """\
diff --git a/src/repeat.js b/src/repeat.js
--- a/src/repeat.js
+++ b/src/repeat.js
@@ -1,0 +2,1 @@
+const duplicate = 1;
@@ -10,0 +12,1 @@
+const duplicate = 1;
"""
    parsed = parse_diff(diff)
    lines = parsed["src/repeat.js"]
    assert lines == ["const duplicate = 1;", "const duplicate = 1;"]
    assert added_file_linenos("src/repeat.js", lines) == [2, 12]


def test_added_line_starting_with_plusplus_is_kept():
    diff = """\
diff --git a/src/counter.js b/src/counter.js
--- a/src/counter.js
+++ b/src/counter.js
@@ -0,0 +1,2 @@
+++counter;
+const total = counter;
"""
    result = parse_diff(diff)
    assert result["src/counter.js"] == ["++counter;", "const total = counter;"]


def test_plain_unified_diff_without_git_header():
    diff = """\
--- a/src/app.js
+++ b/src/app.js
@@ -1 +1,2 @@
+const added = 1;
 const existing = 2;
--- a/src/other.ts
+++ b/src/other.ts
@@ -1 +1,2 @@
+const other = 1;
 const existingOther = 2;
"""
    result = parse_diff(diff)
    assert result["src/app.js"] == ["const added = 1;"]
    assert result["src/other.ts"] == ["const other = 1;"]