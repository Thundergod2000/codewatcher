"""CLI integration tests for whole-project `codewatch scan`."""

import json
from types import SimpleNamespace

from dulwich import porcelain

from codewatch.cli import cmd_scan


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


def test_scan_reviews_whole_project(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path)
    _commit(
        repo,
        {
            "app.py": "def public():\n    return 1\n",
            "app.js": "export function fetchData() {\n    return 1;\n}\n",
        },
        "first",
    )
    monkeypatch.chdir(repo)

    code = cmd_scan(SimpleNamespace(format="text", no_block=False))

    output = capsys.readouterr().out
    assert code == 0
    assert "codewatch: scan — 2 file(s) scanned" in output
    assert "CW-DOC-001" in output


def test_scan_reports_json_mode_and_file_count(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path)
    _commit(repo, {"app.py": "def public():\n    return 1\n"}, "first")
    monkeypatch.chdir(repo)

    code = cmd_scan(SimpleNamespace(format="json", no_block=False))

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["schema_version"] == 1
    assert payload["mode"] == "scan"
    assert payload["files_scanned"] == 1
    assert list(payload["files"]) == ["app.py"]
    checks = {c["check"]: c for c in payload["files"]["app.py"]}
    assert checks["docstrings"]["violations"]


def scan_ignores_node_modules_and_dist(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path)
    _commit(
        repo,
        {
            "app.py": "def public():\n    return 1\n",
            "dist/bad.js": 'const key = "sk-abc123xyz789longkey";\n',
            "node_modules/pkg.js": "const x = 1;\n",
        },
        "first",
    )
    monkeypatch.chdir(repo)

    code = cmd_scan(SimpleNamespace(format="text", no_block=False))

    output = capsys.readouterr().out
    assert code == 0
    # dist/ and node_modules/ are ignored, so no secret error and they are not scanned.
    assert "sk-abc123" not in output
    assert "codewatch: scan — 1 file(s) scanned" in output


def scan_blocks_on_secret_in_tracked_file(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path)
    _commit(
        repo, {"app.py": 'password = "supersecret123"\n'}, "secret"
    )
    monkeypatch.chdir(repo)

    code = cmd_scan(SimpleNamespace(format="text", no_block=False))

    assert code == 1
    output = capsys.readouterr().out
    assert "CW-SECRET-004" in output or "secrets" in output
    assert "FAIL" in output


def scan_no_block_exits_zero_on_error(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path)
    _commit(
        repo, {"app.py": 'password = "supersecret123"\n'}, "secret"
    )
    monkeypatch.chdir(repo)

    code = cmd_scan(SimpleNamespace(format="text", no_block=True))

    assert code == 0
    assert "FAIL" in capsys.readouterr().out


def scan_nothing_to_scan(tmp_path, monkeypatch, capsys):
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

    code = cmd_scan(SimpleNamespace(format="text", no_block=False))

    assert code == 0
    assert "no supported files found" in capsys.readouterr().out
