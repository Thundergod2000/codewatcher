"""Integration tests for the CLI with JavaScript/TypeScript changes."""

import json
from types import SimpleNamespace

from codewatch.cli import cmd_scan


def _diff_for(path: str, added_lines: list[str]) -> str:
    body = "\n".join("+" + line for line in added_lines)
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(added_lines)} @@\n"
        f"{body}\n"
    )


def _run_scan(monkeypatch, diff: str, fmt: str = "text", no_block: bool = False) -> int:
    monkeypatch.setattr("codewatch.cli.get_diff", lambda ref: diff)
    args = SimpleNamespace(diff="HEAD~1", format=fmt, no_block=no_block)
    return cmd_scan(args)


def test_js_secret_fails_in_text_output(tmp_path, monkeypatch, capsys):
    (tmp_path / "app.js").write_text('const apiKey = "sk-abc123xyz789longkey";\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = _run_scan(monkeypatch, _diff_for("app.js", ['const apiKey = "sk-abc123xyz789longkey";']))

    output = capsys.readouterr().out
    assert code == 1
    assert "FAIL" in output
    assert "app.js" in output
    assert "secrets" in output
    assert "ERROR" in output
    assert "line 1" in output


def test_js_secret_with_no_block_exits_zero(tmp_path, monkeypatch, capsys):
    (tmp_path / "app.js").write_text('const apiKey = "sk-abc123xyz789longkey";\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = _run_scan(
        monkeypatch,
        _diff_for("app.js", ['const apiKey = "sk-abc123xyz789longkey";']),
        no_block=True,
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "ERROR" in output


def test_json_output_shape_for_js(tmp_path, monkeypatch, capsys):
    (tmp_path / "app.js").write_text('const apiKey = "sk-abc123xyz789longkey";\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = _run_scan(
        monkeypatch,
        _diff_for("app.js", ['const apiKey = "sk-abc123xyz789longkey";']),
        fmt="json",
    )

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert code == 1
    assert list(payload) == ["app.js"]
    checks = payload["app.js"]
    assert [c["check"] for c in checks] == [
        "secrets",
        "complexity",
        "dead_code",
        "test_presence",
        "docstrings",
    ]
    for check in checks:
        assert set(check) == {"check", "passed", "skipped", "skip_reason", "violations"}
        for violation in check["violations"]:
            assert set(violation) == {"line", "severity", "message"}
    secrets = checks[0]
    assert secrets["passed"] is False
    assert secrets["violations"][0]["severity"] == "error"


def test_mixed_python_and_js_diff_reports_both(tmp_path, monkeypatch, capsys):
    (tmp_path / "app.py").write_text('password = "supersecret123"\n', encoding="utf-8")
    (tmp_path / "app.js").write_text('const token = "abcdefghijklmnop";\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    diff = (
        _diff_for("app.py", ['password = "supersecret123"'])
        + _diff_for("app.js", ['const token = "abcdefghijklmnop";'])
    )
    code = _run_scan(monkeypatch, diff, fmt="json")

    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert set(payload) == {"app.py", "app.js"}
    assert payload["app.py"][0]["violations"]
    assert payload["app.js"][0]["violations"]


def test_clean_js_file_passes(tmp_path, monkeypatch, capsys):
    source = (
        "/** Fetch data. */\n"
        "export function fetchData() {\n"
        "    return process.env.API_URL;\n"
        "}\n"
    )
    (tmp_path / "app.js").write_text(source, encoding="utf-8")
    (tmp_path / "app.test.js").write_text("test('fetch', () => {});\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    added = [
        "/** Fetch data. */",
        "export function fetchData() {",
        "    return process.env.API_URL;",
        "}",
    ]
    code = _run_scan(monkeypatch, _diff_for("app.js", added))

    output = capsys.readouterr().out
    assert code == 0
    assert "All checks passed" in output


def test_no_supported_files_changed(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    diff = (
        "diff --git a/README.md b/README.md\n"
        "--- a/README.md\n"
        "+++ b/README.md\n"
        "@@ -0,0 +1,1 @@\n"
        "+# hello\n"
    )

    code = _run_scan(monkeypatch, diff)

    output = capsys.readouterr().out
    assert code == 0
    assert "no supported files changed" in output


def test_parser_failure_reports_skipped(tmp_path, monkeypatch, capsys):
    (tmp_path / "broken.js").write_text("export function broken( { return 1;\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = _run_scan(
        monkeypatch,
        _diff_for("broken.js", ["export function broken( { return 1;"]),
        fmt="json",
    )

    payload = json.loads(capsys.readouterr().out)
    checks = {c["check"]: c for c in payload["broken.js"]}
    assert code == 0  # skipped checks do not block
    assert checks["complexity"]["skipped"] is True
    assert "syntax" in checks["complexity"]["skip_reason"]
    assert checks["dead_code"]["skipped"] is True
    assert checks["docstrings"]["skipped"] is True