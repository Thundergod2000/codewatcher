"""Tests for the pre-push hook runtime and installer."""

from types import SimpleNamespace

import pytest
from dulwich import porcelain
from dulwich.repo import Repo

from codewatch.cli import _find_git_dir, build_parser, cmd_install_hook
from codewatch.diff import ZERO_SHA, get_push_diff, parse_diff
from codewatch.hook import (
    EXIT_BLOCK,
    EXIT_ERROR,
    EXIT_OK,
    PushRef,
    parse_push_input,
    run_hook,
)

SHA_A = "a" * 40
SHA_B = "b" * 40


def _commit(repo, files, message):
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        porcelain.add(repo, paths=[name])
    sha = porcelain.commit(
        repo,
        message=message.encode(),
        author=b"Test <test@example.com>",
        committer=b"Test <test@example.com>",
    )
    return sha.decode() if isinstance(sha, bytes) else sha


def _make_repo(tmp_path, branch="master"):
    repo = tmp_path / "repo"
    repo.mkdir()
    porcelain.init(repo)
    if branch != "master":
        with Repo(repo) as handle:
            handle.refs.set_symbolic_ref(b"HEAD", f"refs/heads/{branch}".encode())
    return repo


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


def test_parse_push_input_accepts_git_lines():
    refs = parse_push_input(_push_line() + "\n")

    assert refs == [
        PushRef(
            local_ref="refs/heads/main",
            local_sha=SHA_A,
            remote_ref="refs/heads/main",
            remote_sha=ZERO_SHA,
        )
    ]


def test_parse_push_input_rejects_malformed_line():
    with pytest.raises(ValueError):
        parse_push_input("refs/heads/main not-a-sha\n")


def test_get_push_diff_uses_remote_merge_base(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    first = _commit(repo, {"app.py": "a = 1\n"}, "first")
    second = _commit(
        repo,
        {"app.py": 'a = 1\npassword = "supersecret123"\n'},
        "second",
    )
    monkeypatch.chdir(repo)

    changed = parse_diff(get_push_diff(second, first))

    assert changed == {"app.py": ['password = "supersecret123"']}


def test_get_push_diff_new_branch_uses_default_branch(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    base = _commit(repo, {"app.py": "a = 1\n"}, "base")
    with Repo(repo) as handle:
        handle.refs[b"refs/heads/main"] = base.encode()
    tip = _commit(repo, {"feature.py": "b = 2\n"}, "feature")
    monkeypatch.chdir(repo)

    changed = parse_diff(get_push_diff(tip, ZERO_SHA))

    assert changed == {"feature.py": ["b = 2"]}


def test_get_push_diff_caps_new_branch_at_three_commits(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path, branch="feature")
    _commit(repo, {"root_only.py": "x = 0\n"}, "root")
    _commit(repo, {"app.py": "x = 1\n"}, "one")
    _commit(repo, {"app.py": "x = 2\n"}, "two")
    tip = _commit(repo, {"app.py": "x = 3\n"}, "three")
    monkeypatch.chdir(repo)

    diff = get_push_diff(tip, ZERO_SHA)

    assert "root_only.py" not in diff
    assert "x = 3" in diff


def test_get_push_diff_reviews_root_when_branch_is_short(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path, branch="feature")
    _commit(repo, {"root_only.py": "x = 0\n"}, "root")
    tip = _commit(repo, {"app.py": "y = 1\n"}, "second")
    monkeypatch.chdir(repo)

    diff = get_push_diff(tip, ZERO_SHA)

    assert "root_only.py" in diff
    assert "app.py" in diff


@pytest.mark.parametrize("bad_sha", ["x; rm -rf ~", "abc", "g" * 40, ""])
def test_get_push_diff_rejects_invalid_local_sha(tmp_path, monkeypatch, bad_sha):
    repo = _make_repo(tmp_path)
    monkeypatch.chdir(repo)

    with pytest.raises(ValueError):
        get_push_diff(bad_sha, ZERO_SHA)


def test_run_hook_blocks_on_error(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text(
        'password = "supersecret123"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    diff = _diff_for("app.py", ['password = "supersecret123"'])
    monkeypatch.setattr("codewatch.hook.get_push_diff", lambda *args: diff)

    assert run_hook(_push_line()) == EXIT_BLOCK


def test_run_hook_allows_warnings(tmp_path, monkeypatch):
    source = "def public():\n    return 1\n"
    (tmp_path / "app.py").write_text(source, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    diff = _diff_for("app.py", ["def public():", "    return 1"])
    monkeypatch.setattr("codewatch.hook.get_push_diff", lambda *args: diff)

    assert run_hook(_push_line()) == EXIT_OK


def test_run_hook_fails_closed_on_tool_error(monkeypatch):
    def boom(*args):
        raise RuntimeError("cannot read repo")

    monkeypatch.setattr("codewatch.hook.get_push_diff", boom)

    assert run_hook(_push_line()) == EXIT_ERROR


def test_run_hook_fails_closed_on_bad_config(tmp_path, monkeypatch):
    (tmp_path / "codewatch.yaml").write_text("version: 2\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def boom(*args):
        raise AssertionError("scan must not run with an invalid config")

    monkeypatch.setattr("codewatch.hook.get_push_diff", boom)

    assert run_hook(_push_line()) == EXIT_ERROR


def test_run_hook_skips_deleted_refs(monkeypatch):
    def boom(*args):
        raise AssertionError("deleted refs must not be scanned")

    monkeypatch.setattr("codewatch.hook.get_push_diff", boom)

    assert run_hook(_push_line(local_sha=ZERO_SHA, remote_sha=SHA_B)) == EXIT_OK


def test_run_hook_rejects_malformed_input():
    assert run_hook("refs/heads/main not-a-sha\n") == EXIT_ERROR


def test_install_hook_writes_managed_shim(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    _commit(repo, {"app.py": "a = 1\n"}, "first")
    monkeypatch.chdir(repo)

    assert cmd_install_hook(SimpleNamespace()) == 0

    hook = repo / ".git" / "hooks" / "pre-push"
    script = hook.read_text(encoding="utf-8")
    assert script.startswith("#!/bin/sh\n")
    assert "# codewatch-managed" in script
    assert "-m codewatch hook" in script
    assert "HEAD~1" not in script
    assert "--ref" not in script


def test_install_hook_is_idempotent(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    _commit(repo, {"app.py": "a = 1\n"}, "first")
    monkeypatch.chdir(repo)
    hook = repo / ".git" / "hooks" / "pre-push"

    cmd_install_hook(SimpleNamespace())
    first = hook.read_text(encoding="utf-8")
    cmd_install_hook(SimpleNamespace())

    assert hook.read_text(encoding="utf-8") == first
    assert not (hook.parent / "pre-push.codewatch-local").exists()


def test_install_hook_preserves_existing_hook(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    _commit(repo, {"app.py": "a = 1\n"}, "first")
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    legacy = "#!/bin/sh\necho legacy\n"
    (hooks / "pre-push").write_text(legacy, encoding="utf-8", newline="\n")
    monkeypatch.chdir(repo)

    cmd_install_hook(SimpleNamespace())
    cmd_install_hook(SimpleNamespace())

    backup = hooks / "pre-push.codewatch-local"
    assert backup.read_text(encoding="utf-8") == legacy
    script = (hooks / "pre-push").read_text(encoding="utf-8")
    assert "pre-push.codewatch-local" in script
    assert "backup_status" in script


def test_find_git_dir_uses_common_dir_for_worktrees(tmp_path, monkeypatch):
    common = tmp_path / "common"

    class FakeRepo:
        def commondir(self):
            return str(common / "worktrees" / "feature" / ".." / "..")

        def controldir(self):
            return str(tmp_path / "wrong")

        def close(self):
            pass

    monkeypatch.setattr("codewatch.cli.Repo.discover", lambda start: FakeRepo())

    assert _find_git_dir() == str(common.resolve())


def test_install_hook_outside_repo(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("codewatch.cli._find_git_dir", lambda: None)

    assert cmd_install_hook(SimpleNamespace()) == 1

    assert ".git not found" in capsys.readouterr().err


def test_install_hook_no_longer_accepts_ref():
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["install-hook", "--ref", "main"])


def test_hook_subcommand_exists():
    assert build_parser().parse_args(["hook"]).command == "hook"
