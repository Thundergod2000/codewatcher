"""CLI integration tests for codewatch.yaml."""

import json
from types import SimpleNamespace

from codewatch.cli import cmd_check


def _diff_for(path: str, added_lines: list[str]) -> str:
    body = "\n".join("+" + line for line in added_lines)
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(added_lines)} @@\n"
        f"{body}\n"
    )


def _run_check(
    monkeypatch, diff: str, fmt: str = "text", no_block: bool = False
) -> int:
    monkeypatch.setattr("codewatch.cli.get_diff", lambda ref: diff)
    args = SimpleNamespace(base=None, format=fmt, no_block=no_block)
    return cmd_check(args)


def test_invalid_config_exits_two(tmp_path, monkeypatch, capsys):
    (tmp_path / "codewatch.yaml").write_text("version: 2\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = _run_check(monkeypatch, _diff_for("app.py", ["x = 1"]))

    assert code == 2
    assert "unsupported version" in capsys.readouterr().err


def test_config_allowlist_suppresses_secret(tmp_path, monkeypatch, capsys):
    (tmp_path / "codewatch.yaml").write_text(
        "version: 1\n"
        "allow:\n"
        "  - path: 'app.py'\n"
        "    checks: [secrets]\n"
        "    reason: 'test fixture'\n",
        encoding="utf-8",
    )
    line = 'password = "supersecret123"'
    (tmp_path / "app.py").write_text(line + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = _run_check(monkeypatch, _diff_for("app.py", [line]))

    output = capsys.readouterr().out
    assert code == 0
    assert "suppressed 1 violation(s) (config: 1)" in output


def test_json_reports_suppression_reason(tmp_path, monkeypatch, capsys):
    (tmp_path / "codewatch.yaml").write_text(
        "version: 1\n"
        "allow:\n"
        "  - path: 'app.py'\n"
        "    checks: [secrets]\n",
        encoding="utf-8",
    )
    line = 'password = "supersecret123"'
    (tmp_path / "app.py").write_text(line + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = _run_check(monkeypatch, _diff_for("app.py", [line]), fmt="json")

    payload = json.loads(capsys.readouterr().out)
    secrets = payload["files"]["app.py"][0]
    assert code == 0
    assert secrets["suppressed"] == {"config": 1}
    assert secrets["violations"] == []
