"""Stage 4: cyclomatic complexity delta tests."""

import pytest

from codewatch.checks.complexity import check_complexity
from codewatch.checks.js_complexity import check_js_complexity
from codewatch.scanner import run_checks
from codewatch.types import Severity


def _py_source(branches: int = 21, name: str = "run") -> str:
    lines = [f"def {name}(x):"]
    for i in range(branches):
        lines.append(f"    if x == {i}:")
        lines.append(f"        return {i}")
    lines.append("    return -1")
    return "\n".join(lines)


def test_python_unchanged_over_limit_warns_but_does_not_block(tmp_path):
    current = _py_source(branches=21)  # complexity 22
    base = _py_source(branches=21)  # unchanged
    path = str(tmp_path / "app.py")
    open(path, "w", encoding="utf-8").write(current)

    result = check_complexity(path, current.splitlines(), base_source=base)

    errors = [v for v in result.violations if v.severity == Severity.ERROR]
    assert errors == []
    warnings = [v for v in result.violations if v.severity == Severity.WARNING]
    assert len(warnings) == 1
    assert warnings[0].rule_id == "CW-COMPLEX-002"
    assert "pre-existing" in warnings[0].message
    assert result.passed is True


def test_python_increased_complexity_blocks(tmp_path):
    base = _py_source(branches=20)  # complexity 21
    current = _py_source(branches=21)  # complexity 22, increased
    path = str(tmp_path / "app.py")
    open(path, "w", encoding="utf-8").write(current)

    result = check_complexity(path, current.splitlines(), base_source=base)

    errors = [v for v in result.violations if v.severity == Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule_id == "CW-COMPLEX-001"
    assert result.passed is False


def test_python_new_function_over_limit_blocks(tmp_path):
    base = "x = 1\n"  # no run() function
    current = _py_source(branches=21)
    path = str(tmp_path / "app.py")
    open(path, "w", encoding="utf-8").write(current)

    result = check_complexity(path, current.splitlines(), base_source=base)

    errors = [v for v in result.violations if v.severity == Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule_id == "CW-COMPLEX-001"
    assert result.passed is False


def test_python_no_base_source_still_blocks_over_limit(tmp_path):
    current = _py_source(branches=21)
    path = str(tmp_path / "app.py")
    open(path, "w", encoding="utf-8").write(current)

    result = check_complexity(path, current.splitlines())

    errors = [v for v in result.violations if v.severity == Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule_id == "CW-COMPLEX-001"
    assert result.passed is False


def test_python_decreased_complexity_warns(tmp_path):
    base = _py_source(branches=22)  # complexity 23
    current = _py_source(branches=21)  # complexity 22, decreased
    path = str(tmp_path / "app.py")
    open(path, "w", encoding="utf-8").write(current)

    result = check_complexity(path, current.splitlines(), base_source=base)

    errors = [v for v in result.violations if v.severity == Severity.ERROR]
    assert errors == []
    warnings = [v for v in result.violations if v.severity == Severity.WARNING]
    assert len(warnings) == 1
    assert warnings[0].rule_id == "CW-COMPLEX-002"
    assert result.passed is True


def test_scanner_applies_delta_via_base_sources(tmp_path):
    current = _py_source(branches=21)
    base = _py_source(branches=21)
    path = str(tmp_path / "app.py")
    open(path, "w", encoding="utf-8").write(current)

    results = run_checks(
        {"app.py": current.splitlines()}, base_sources={"app.py": base}
    )

    docs = results["app.py"][1]  # complexity
    errors = [v for v in docs.violations if v.severity == Severity.ERROR]
    assert errors == []
    assert docs.passed is True


def _js_source(branches: int = 21, name: str = "run") -> str:
    lines = [f"function {name}(x) {{"]
    for i in range(branches):
        lines.append(f"  if (x === {i}) return {i};")
    lines.append("  return -1;")
    lines.append("}")
    return "\n".join(lines)


def test_js_unchanged_over_limit_warns(tmp_path):
    current = _js_source(branches=21)
    base = _js_source(branches=21)
    path = str(tmp_path / "app.js")
    open(path, "w", encoding="utf-8").write(current)

    result = check_js_complexity(path, current.splitlines(), base_source=base)

    errors = [v for v in result.violations if v.severity == Severity.ERROR]
    assert errors == []
    warnings = [v for v in result.violations if v.severity == Severity.WARNING]
    assert len(warnings) == 1
    assert warnings[0].rule_id == "CW-COMPLEX-002"
    assert "pre-existing" in warnings[0].message
    assert result.passed is True


def test_js_increased_complexity_blocks(tmp_path):
    base = _js_source(branches=20)
    current = _js_source(branches=21)
    path = str(tmp_path / "app.js")
    open(path, "w", encoding="utf-8").write(current)

    result = check_js_complexity(path, current.splitlines(), base_source=base)

    errors = [v for v in result.violations if v.severity == Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule_id == "CW-COMPLEX-001"
    assert result.passed is False


def test_js_new_function_over_limit_blocks(tmp_path):
    base = "const x = 1;\n"
    current = _js_source(branches=21)
    path = str(tmp_path / "app.js")
    open(path, "w", encoding="utf-8").write(current)

    result = check_js_complexity(path, current.splitlines(), base_source=base)

    errors = [v for v in result.violations if v.severity == Severity.ERROR]
    assert len(errors) == 1
    assert errors[0].rule_id == "CW-COMPLEX-001"
    assert result.passed is False
