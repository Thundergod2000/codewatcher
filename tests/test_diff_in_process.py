"""Tests that git data is read in-process, without launching an executable."""

import subprocess
from pathlib import Path

from dulwich import porcelain

from codewatch.diff import get_changed_files, get_diff, parse_diff

PACKAGE = Path(__file__).resolve().parents[1] / "codewatch"
FORBIDDEN = ("import subprocess", "subprocess.", "os.system", "os.popen", "Popen(")


def _commit(repo, files, message):
    for name, content in files.items():
        (repo / name).write_text(content, encoding="utf-8")
        porcelain.add(repo, paths=[name])
    return porcelain.commit(
        repo,
        message=message.encode(),
        author=b"Test <test@example.com>",
        committer=b"Test <test@example.com>",
    )


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    porcelain.init(repo)
    _commit(repo, {"app.py": "a = 1\n"}, "first")
    _commit(repo, {"app.py": 'a = 1\npassword = "supersecret123"\n'}, "second")
    return repo


def _no_process(*args, **kwargs):
    raise AssertionError("codewatch must not launch an external process")


def test_get_diff_reads_repo_without_subprocess(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(subprocess, "run", _no_process)
    monkeypatch.setattr(subprocess, "Popen", _no_process)

    parsed = parse_diff(get_diff("HEAD~1"))

    assert parsed == {"app.py": ['password = "supersecret123"']}


def test_get_diff_supports_double_and_triple_dot_ranges(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

    double_dot = parse_diff(get_diff("HEAD~1..HEAD"))
    triple_dot = parse_diff(get_diff("HEAD~1...HEAD"))

    assert double_dot == triple_dot
    assert triple_dot == {"app.py": ['password = "supersecret123"']}


def test_get_diff_falls_back_to_staged_changes(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    (repo / "app.py").write_text(
        'a = 1\npassword = "supersecret123"\nstaged = True\n', encoding="utf-8"
    )
    porcelain.add(repo, paths=["app.py"])
    monkeypatch.chdir(repo)

    parsed = parse_diff(get_diff("not-a-real-ref"))

    assert parsed == {"app.py": ["staged = True"]}


def test_get_changed_files_reads_worktree_without_subprocess(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    (repo / "app.py").write_text("a = 2\n", encoding="utf-8")
    (repo / "notes.txt").write_text("ignored\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    monkeypatch.setattr(subprocess, "run", _no_process)

    assert get_changed_files("HEAD") == ["app.py"]


def test_package_source_never_imports_subprocess():
    for path in PACKAGE.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in source, f"{path} uses {token}"
