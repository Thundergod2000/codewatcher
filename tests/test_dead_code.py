"""Tests for dead code check — only newly added functions."""

from codewatch.checks.dead_code import check_dead_code
from codewatch.types import Severity

UNUSED_SOURCE = """\
def unused_helper(x, y):
    return x + y
"""

UNUSED_ADDED_LINES = [
    "def unused_helper(x, y):",
    "    return x + y",
]


def test_unused_function_in_added_lines_flagged(tmp_path, monkeypatch):
    src = tmp_path / "mod.py"
    src.write_text(UNUSED_SOURCE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_dead_code("mod.py", UNUSED_ADDED_LINES)
    assert result.passed  # dead code warns, never blocks
    assert len(result.violations) == 1
    assert result.violations[0].severity == Severity.WARNING
    assert result.violations[0].line == 1
    assert "unused_helper" in result.violations[0].message


def test_absolute_path_resolves_vulture_finding(tmp_path, monkeypatch):
    src = tmp_path / "mod.py"
    src.write_text(UNUSED_SOURCE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_dead_code(str(src), UNUSED_ADDED_LINES)
    assert len(result.violations) == 1


def test_preexisting_dead_code_not_flagged(tmp_path, monkeypatch):
    src = tmp_path / "mod.py"
    src.write_text(
        "def old_unused():\n"
        "    return 1\n"
        "\n"
        "\n"
        "def ping():\n"
        "    return 1\n"
        "\n"
        "\n"
        "ping()\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    result = check_dead_code("mod.py", ["def ping():", "    return 1", "ping()"])
    assert result.violations == []


def test_missing_file_skips_check(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = check_dead_code("missing.py", [])
    assert result.skipped
    assert result.skip_reason


def test_nightmare_file_reports_unused_code():
    with open("demo/nightmare_code.py", encoding="utf-8") as f:
        result = check_dead_code("demo/nightmare_code.py", f.read().splitlines())
    assert result.skipped is False
    unused = [v for v in result.violations if "Unused" in v.message]
    assert unused
    assert any("Unused function" in v.message for v in unused)
