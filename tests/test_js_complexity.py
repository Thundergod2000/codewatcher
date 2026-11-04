"""Tests for JS/TS complexity check."""

from codewatch.checks.js_complexity import check_js_complexity


# Simple function
SIMPLE_JS = """
function ping() {
    return 1;
}
"""

# Complex function (nested conditionals)
COMPLEX_JS = """
function complexFunction(a, b, c, d, e, f, g) {
    if (a) {
        if (b) {
            if (c) {
                for (const x of d) {
                    if (e) {
                        if (f === 1) {
                            return x;
                        } else if (f === 2) {
                            return x * 2;
                        } else if (f === 3) {
                            return x * 3;
                        } else if (f === 4) {
                            return x * 6;
                        } else {
                            if (g) {
                                return x * 4;
                            } else {
                                return x * 5;
                            }
                        }
                    }
                }
            }
        }
    }
    return null;
}
"""

# Arrow function
ARROW_JS = """
const complexArrow = (a, b, c, d, e, f, g) => {
    if (a) {
        if (b) {
            if (c) {
                for (const x of d) {
                    if (e) {
                        if (f === 1) {
                            return x;
                        } else if (f === 2) {
                            return x * 2;
                        } else if (f === 3) {
                            return x * 3;
                        } else if (f === 4) {
                            return x * 6;
                        } else {
                            if (g) {
                                return x * 4;
                            } else {
                                return x * 5;
                            }
                        }
                    }
                }
            }
        }
    }
    return null;
};
"""

# TypeScript
TS_COMPLEX = """
function complexFunction(a: number, b: number, c: number): number {
    if (a > 0) {
        if (b > 0) {
            if (c > 0) {
                for (let i = 0; i < 10; i++) {
                    if (i % 2 === 0 && a > 1) {
                        switch (i) {
                            case 1:
                                return 1;
                            case 2:
                                return 2;
                            case 3:
                                return 3;
                            case 4:
                                return 4;
                        }
                    } else if (i % 3 === 0 || b > 2) {
                        return i;
                    } else if (i % 5 === 0) {
                        return i;
                    }
                }
            }
        }
    }
    return -1;
}
"""


def test_old_complex_function_ignored(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text(COMPLEX_JS + SIMPLE_JS, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_complexity("mod.js", ["function ping() {"])
    assert result.violations == []


def test_new_complex_function_flagged(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text(COMPLEX_JS, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    added = COMPLEX_JS.strip().splitlines()
    result = check_js_complexity("mod.js", added)
    assert result.violations
    assert result.violations[0].line == 2  # function starts at line 2
    # Should be ERROR (>20) or WARNING (>10)
    assert result.violations[0].severity in ("error", "warn")


def test_arrow_function_complexity(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text(ARROW_JS, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    added = ARROW_JS.strip().splitlines()
    result = check_js_complexity("mod.js", added)
    assert result.violations
    assert result.violations[0].line == 2


def test_typescript_complexity(tmp_path, monkeypatch):
    src = tmp_path / "mod.ts"
    src.write_text(TS_COMPLEX, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    added = TS_COMPLEX.strip().splitlines()
    result = check_js_complexity("mod.ts", added)
    assert result.violations
    assert result.violations[0].line == 2


def test_edit_outside_function_not_flagged(tmp_path, monkeypatch):
    """Editing a line outside a function should not flag the function."""
    src = tmp_path / "mod.js"
    src.write_text(COMPLEX_JS + "\n// comment\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # Only the comment line is added
    result = check_js_complexity("mod.js", ["// comment"])
    assert result.violations == []


def test_simple_function_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text(SIMPLE_JS, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    added = SIMPLE_JS.strip().splitlines()
    result = check_js_complexity("mod.js", added)
    assert result.violations == []


def test_missing_file_skips(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = check_js_complexity("missing.js", ["const x = 1;"])
    assert result.skipped
    assert "not found" in result.skip_reason


def test_syntax_error_skips(tmp_path, monkeypatch):
    src = tmp_path / "broken.js"
    src.write_text("function broken( { return 1;\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_complexity("broken.js", ["function broken( {"])
    assert result.skipped
    assert "syntax" in result.skip_reason