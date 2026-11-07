"""CLI and hook integration tests for the baseline."""

import json
from types import SimpleNamespace

from dulwich import porcelain

from codewatch.cli import cmd_baseline, cmd_check
from codewatch.diff import ZERO_SHA
from codewatch.hook import EXIT_ERROR, EXIT_OK, run_hook
from codewatch.types import make_fingerprint

SHA_A = "a" * 40


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    porcelain.init(repo)
    return repo


def _commit(repo, files, message):
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        porcelain.add(repo, paths=[name])
    porcelain.commit(
        repo,
        message=message.encode(),
        author=b"Test <test@example.com>",
        committer=b"Test <test@example.com>",
    )


def _diff_for(path: str, added_lines: list[str]) -> str:
    body = "\n".join("+" + line for line in added_lines)
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(added_lines)} @@\n"
        f"{body}\n"
    )


def _push_line(local_sha=SHA_A, remote_sha=ZERO_SHA, ref="refs/heads/main"):
    return f"{ref} {local_sha} {ref} {remote_sha}\n"


def test_baseline_write_scans_whole_project(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path)
    _commit(repo, {"app.py": "def public():\n    return 1\n"}, "first")
    monkeypatch.chdir(repo)

    code = cmd_baseline(SimpleNamespace(action="write", diff=None))

    assert code == 0
    data = json.loads((repo / ".codewatch-baseline.json").read_text(encoding="utf-8"))
    rules = {entry["rule_id"] for entry in data["entries"]}
    assert "CW-DOC-001" in rules
    assert all(not rule.startswith("CW-SECRET-") for rule in rules)
    assert "baseline written" in capsys.readouterr().out


def test_baseline_write_never_records_secret_values(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    _commit(repo, {"app.py": 'password = "supersecret123"\n'}, "secret")
    monkeypatch.chdir(repo)

    assert cmd_baseline(SimpleNamespace(action="write", diff=None)) == 0

    text = (repo / ".codewatch-baseline.json").read_text(encoding="utf-8")
    assert "CW-SECRET" not in text
    assert "supersecret123" not in text


def test_baseline_update_rewrites_entries(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    _commit(repo, {"app.py": "def public():\n    return 1\n"}, "first")
    monkeypatch.chdir(repo)
    assert cmd_baseline(SimpleNamespace(action="write", diff=None)) == 0

    _commit(
        repo,
        {"app.py": "def public():\n    return 1\n\n\ndef second():\n    return 2\n"},
        "second",
    )
    assert cmd_baseline(SimpleNamespace(action="update", diff=None)) == 0

    data = json.loads((repo / ".codewatch-baseline.json").read_text(encoding="utf-8"))
    functions = {
        entry.get("function")
        for entry in data["entries"]
        if entry["rule_id"] == "CW-DOC-001"
    }
    assert {"public", "second"} <= functions


def test_scan_applies_baseline(tmp_path, monkeypatch, capsys):
    fingerprint = make_fingerprint("CW-DOC-001", "app.py", "public")
    (tmp_path / "app.py").write_text("def public():\n    return 1\n", encoding="utf-8")
    (tmp_path / ".codewatch-baseline.json").write_text(
        json.dumps({
            "schema_version": 1,
            "generated_at": "2026-01-01T00:00:00Z",
            "entries": [
                {
                    "rule_id": "CW-DOC-001",
                    "file": "app.py",
                    "fingerprint": fingerprint,
                }
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "codewatch.cli.get_diff", lambda ref: _diff_for("app.py", ["def public():"])
    )

    code = cmd_check(SimpleNamespace(base=None, format="text", no_block=False))

    output = capsys.readouterr().out
    assert code == 0
    assert "suppressed 1 violation(s) (baseline: 1)" in output


def test_scan_rejects_secret_baseline(tmp_path, monkeypatch, capsys):
    (tmp_path / ".codewatch-baseline.json").write_text(
        json.dumps({
            "schema_version": 1,
            "entries": [
                {
                    "rule_id": "CW-SECRET-004",
                    "file": "app.py",
                    "fingerprint": "sha256:secret",
                }
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    code = cmd_check(SimpleNamespace(base=None, format="text", no_block=False))

    assert code == 2
    assert "secrets are never suppressed" in capsys.readouterr().err


def test_hook_fails_closed_on_bad_baseline(tmp_path, monkeypatch):
    (tmp_path / ".codewatch-baseline.json").write_text("{bad", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def boom(*args):
        raise AssertionError("scan must not run with an invalid baseline")

    monkeypatch.setattr("codewatch.hook.get_push_diff", boom)

    assert run_hook(_push_line()) == EXIT_ERROR


def test_hook_warns_about_stale_baseline(tmp_path, monkeypatch, capsys):
    stale = make_fingerprint("CW-DOC-001", "app.py", "gone")
    (tmp_path / "app.py").write_text("def public():\n    return 1\n", encoding="utf-8")
    (tmp_path / ".codewatch-baseline.json").write_text(
        json.dumps({
            "schema_version": 1,
            "entries": [
                {
                    "rule_id": "CW-DOC-001",
                    "file": "app.py",
                    "fingerprint": stale,
                }
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "codewatch.hook.get_push_diff",
        lambda *args: _diff_for("app.py", ["def public():"]),
    )

    assert run_hook(_push_line()) == EXIT_OK

    error = capsys.readouterr().err
    assert "stale baseline entry CW-DOC-001" in error
    assert "app.py" in error
