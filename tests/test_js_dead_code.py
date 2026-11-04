"""Tests for JS/TS dead code check."""

from codewatch.checks.js_dead_code import check_js_dead_code
from codewatch.types import Severity

UNUSED_FUNCTION = """\
function unusedHelper() {
    return 1;
}
"""

UNUSED_VARIABLE = """\
const unusedValue = 42;
"""

UNUSED_ARROW = """\
const unusedArrow = () => 1;
"""


def test_unused_function_flagged(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text(UNUSED_FUNCTION, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    added = UNUSED_FUNCTION.strip().splitlines()
    result = check_js_dead_code("mod.js", added)
    assert result.passed  # warns, never blocks
    assert len(result.violations) == 1
    assert result.violations[0].severity == Severity.WARNING
    assert result.violations[0].line == 1
    assert "unusedHelper" in result.violations[0].message


def test_unused_variable_flagged(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text(UNUSED_VARIABLE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_dead_code("mod.js", ["const unusedValue = 42;"])
    assert len(result.violations) == 1
    assert "unusedValue" in result.violations[0].message


def test_unused_arrow_function_flagged(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text(UNUSED_ARROW, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_dead_code("mod.js", ["const unusedArrow = () => 1;"])
    assert len(result.violations) == 1
    assert "unusedArrow" in result.violations[0].message


def test_used_function_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text(
        "function usedHelper() {\n"
        "    return 1;\n"
        "}\n"
        "\n"
        "usedHelper();\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_dead_code("mod.js", ["function usedHelper() {"])
    assert result.violations == []


def test_exported_function_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text(
        "export function publicHelper() {\n"
        "    return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_dead_code("mod.js", ["export function publicHelper() {"])
    assert result.violations == []


def test_exported_via_clause_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text(
        "function specHelper() {\n"
        "    return 1;\n"
        "}\n"
        "\n"
        "export { specHelper };\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_dead_code("mod.js", ["function specHelper() {"])
    assert result.violations == []


def test_react_component_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "Button.jsx"
    src.write_text(
        "function Button() {\n"
        "    return null;\n"
        "}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_dead_code("Button.jsx", ["function Button() {"])
    assert result.violations == []


def test_exported_ts_component_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "Button.tsx"
    src.write_text(
        "export const Button = () => <button>Click</button>;\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_dead_code("Button.tsx", ["export const Button = () => <button>Click</button>;"])
    assert result.violations == []


def test_preexisting_dead_code_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text(
        "function oldUnused() {\n"
        "    return 1;\n"
        "}\n"
        "\n"
        "function newUsed() {\n"
        "    return 2;\n"
        "}\n"
        "\n"
        "newUsed();\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_js_dead_code("mod.js", ["function newUsed() {"])
    assert result.violations == []


def test_destructuring_declaration_skipped(tmp_path, monkeypatch):
    src = tmp_path / "mod.js"
    src.write_text("const { first, second } = config;\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_dead_code("mod.js", ["const { first, second } = config;"])
    assert result.violations == []


def test_missing_file_skips(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = check_js_dead_code("missing.js", ["const x = 1;"])
    assert result.skipped
    assert "not found" in result.skip_reason


def test_syntax_error_skips(tmp_path, monkeypatch):
    src = tmp_path / "broken.js"
    src.write_text("function broken( { return 1;\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_dead_code("broken.js", ["function broken( {"])
    assert result.skipped
    assert "syntax" in result.skip_reason