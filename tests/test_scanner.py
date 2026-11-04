"""Tests for language dispatch in the scanner."""

import subprocess

from codewatch.scanner import run_checks, should_block
from codewatch.types import CheckResult, Severity, Violation

EXPECTED_CHECKS = ["secrets", "complexity", "dead_code", "test_presence", "docstrings"]


def test_python_file_uses_python_checks(tmp_path, monkeypatch):
    src = tmp_path / "app.py"
    src.write_text('password = "supersecret123"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    results = run_checks({"app.py": ['password = "supersecret123"']})
    assert list(results) == ["app.py"]
    assert [r.check_name for r in results["app.py"]] == EXPECTED_CHECKS
    assert results["app.py"][0].violations[0].severity == Severity.ERROR


def test_js_file_uses_js_checks(tmp_path, monkeypatch):
    src = tmp_path / "app.js"
    src.write_text(
        "/** Fetch. */\n"
        "export function fetchData() {\n"
        "    return 1;\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "app.test.js").write_text("test('x', () => {});\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    results = run_checks({"app.js": ["export function fetchData() {"]})
    assert [r.check_name for r in results["app.js"]] == EXPECTED_CHECKS
    test_result = results["app.js"][3]
    assert test_result.violations == []  # JS test discovery, not Python


def test_ts_file_uses_js_checks(tmp_path, monkeypatch):
    src = tmp_path / "utils.ts"
    src.write_text("export const helper = (): number => 1;\n", encoding="utf-8")
    (tmp_path / "utils.test.ts").write_text("test('x', () => {});\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    results = run_checks({"utils.ts": ["export const helper = (): number => 1;"]})
    assert [r.check_name for r in results["utils.ts"]] == EXPECTED_CHECKS
    # No JSDoc -> documentation warning from the JS check
    assert results["utils.ts"][4].violations


def test_tsx_file_runs_js_checks(tmp_path, monkeypatch):
    src = tmp_path / "Button.tsx"
    src.write_text(
        "/** Button. */\n"
        "export const Button = () => <button>Click</button>;\n",
        encoding="utf-8",
    )
    (tmp_path / "Button.test.tsx").write_text("test('b', () => {});\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    results = run_checks({"Button.tsx": ["export const Button = () => <button>Click</button>;"]})
    assert [r.check_name for r in results["Button.tsx"]] == EXPECTED_CHECKS


def test_mixed_python_and_js_files(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text('api_key = "sk-abc123xyz789longkey"\n', encoding="utf-8")
    (tmp_path / "app.js").write_text('const apiKey = "sk-abc123xyz789longkey";\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    results = run_checks({
        "app.py": ['api_key = "sk-abc123xyz789longkey"'],
        "app.js": ['const apiKey = "sk-abc123xyz789longkey";'],
    })
    assert set(results) == {"app.py", "app.js"}
    assert results["app.py"][0].violations
    assert results["app.js"][0].violations
    assert should_block(results)


def test_unknown_extension_ignored(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    results = run_checks({"README.md": ["# hello"]})
    assert results == {}


def test_should_block_ignores_warnings_only():
    warning_only = {
        "app.js": [
            CheckResult(
                check_name="dead_code",
                passed=True,
                violations=[Violation(line=1, message="unused", severity=Severity.WARNING)],
            )
        ]
    }
    assert should_block(warning_only) is False

    with_error = {
        "app.js": [
            CheckResult(
                check_name="secrets",
                passed=False,
                violations=[Violation(line=1, message="secret", severity=Severity.ERROR)],
            )
        ]
    }
    assert should_block(with_error) is True


def test_checks_run_without_spawning_processes(tmp_path, monkeypatch):
    """Parsing is in-process: no Node, npm, or other subprocess at scan time."""
    src = tmp_path / "app.ts"
    src.write_text("export const add = (a: number): number => a + 1;\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def _fail(*args, **kwargs):
        raise AssertionError("checks must not spawn subprocesses")

    monkeypatch.setattr(subprocess, "run", _fail)
    results = run_checks({"app.ts": ["export const add = (a: number): number => a + 1;"]})
    assert results["app.ts"]