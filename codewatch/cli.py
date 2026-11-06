"""CLI entry point — codewatch scan --diff HEAD~1"""

from __future__ import annotations
import argparse
import os
import stat
import sys
from pathlib import Path

from dulwich.errors import NotGitRepository
from dulwich.repo import Repo

from codewatch.diff import get_diff, parse_diff
from codewatch.hook import run_hook
from codewatch.scanner import run_checks, should_block
from codewatch.reporter import print_results, _ensure_utf8_output

_HOOK_MARKER = "# codewatch-managed"
_HOOK_BACKUP = "pre-push.codewatch-local"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codewatch",
        description="Offline code governance for Python, JavaScript, TypeScript, JSX and TSX — catches quality issues before they reach your repo",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # codewatch scan
    scan = sub.add_parser("scan", help="Scan a git diff for quality issues")
    scan.add_argument(
        "--diff",
        default="HEAD~1",
        metavar="REF",
        help="Git ref to diff against (default: HEAD~1)",
    )
    scan.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    scan.add_argument(
        "--no-block",
        action="store_true",
        help="Always exit 0, even on errors (useful in warn-only mode)",
    )

    # codewatch install-hook
    sub.add_parser(
        "install-hook",
        help="Install a managed pre-push git hook in the current repo",
    )

    # codewatch hook (called by the installed pre-push hook)
    sub.add_parser(
        "hook",
        help="Run the pre-push hook (reads refs from stdin)",
    )

    return parser


def cmd_scan(args: argparse.Namespace) -> int:
    raw_diff = get_diff(args.diff)

    if not raw_diff.strip():
        print("codewatch: no diff found — nothing to review")
        return 0

    changed_files = parse_diff(raw_diff)

    if not changed_files:
        print("codewatch: no supported files changed — nothing to review")
        return 0

    results = run_checks(changed_files)
    print_results(results, fmt=args.format)

    if args.no_block:
        return 0

    return 1 if should_block(results) else 0


def _find_git_dir() -> str | None:
    """Return the common git dir, so linked worktrees share one hook."""
    try:
        repo = Repo.discover(".")
    except (NotGitRepository, OSError):
        return None
    try:
        return str(Path(repo.commondir()).resolve())
    finally:
        repo.close()


def _is_managed(hook_path: str) -> bool:
    try:
        with open(hook_path, encoding="utf-8", errors="replace") as handle:
            return _HOOK_MARKER in handle.read(512)
    except OSError:
        return False


def _sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _make_executable(path: str) -> None:
    """Git for Windows ignores this, but Unix needs the exec bit."""
    try:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def _hook_script(python_exe: str, backup_path: str | None) -> str:
    """Build the managed shim. No ref or SHA is ever written into it."""
    python_cmd = _sh_quote(Path(python_exe).as_posix())
    lines = [
        "#!/bin/sh",
        f"{_HOOK_MARKER} - installed by codewatch-lite",
        "set -u",
        'input=$(mktemp "${TMPDIR:-/tmp}/codewatch-push.XXXXXX") || {',
        '    echo "codewatch: could not create temp file" >&2',
        "    exit 2",
        "}",
        "trap 'rm -f \"$input\"' EXIT HUP INT TERM",
        'cat > "$input" || {',
        '    echo "codewatch: could not read refs from stdin" >&2',
        "    exit 2",
        "}",
        f'{python_cmd} -m codewatch hook < "$input"',
        "status=$?",
        'if [ "$status" -ne 0 ] && [ "$status" -ne 1 ]; then',
        "    status=2",
        "fi",
    ]

    if backup_path is not None:
        backup_cmd = _sh_quote(Path(backup_path).as_posix())
        lines.extend([
            f"if [ -x {backup_cmd} ]; then",
            f'    {backup_cmd} < "$input"',
            "    backup_status=$?",
            '    if [ "$status" -eq 0 ] && [ "$backup_status" -ne 0 ]; then',
            "        status=$backup_status",
            "    fi",
            "fi",
        ])

    lines.extend(['exit "$status"', ""])
    return "\n".join(lines)


def cmd_install_hook(args: argparse.Namespace) -> int:
    _ensure_utf8_output()
    git_dir = _find_git_dir()
    if git_dir is None:
        print("codewatch: .git not found — are you in a git repo?", file=sys.stderr)
        return 1

    hook_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hook_dir, exist_ok=True)
    hook_path = os.path.join(hook_dir, "pre-push")
    backup_path = os.path.join(hook_dir, _HOOK_BACKUP)

    backup: str | None = None
    if os.path.exists(hook_path) and not _is_managed(hook_path):
        if os.path.exists(backup_path):
            print(
                "codewatch: both pre-push and its backup exist — refusing to overwrite",
                file=sys.stderr,
            )
            return 1
        os.replace(hook_path, backup_path)
        backup = backup_path
        _make_executable(backup)
    elif os.path.exists(backup_path):
        backup = backup_path

    python_exe = sys.executable or "python"
    with open(hook_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_hook_script(python_exe, backup))
    _make_executable(hook_path)

    print(f"✓  pre-push hook installed at {hook_path}")
    if backup is not None:
        print(f"   Existing hook preserved at {backup} and will run after codewatch.")
    print("   Every push will now be reviewed by codewatch.")
    return 0


def main() -> None:
    _ensure_utf8_output()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        sys.exit(cmd_scan(args))
    elif args.command == "install-hook":
        sys.exit(cmd_install_hook(args))
    elif args.command == "hook":
        sys.exit(run_hook(sys.stdin.read()))


if __name__ == "__main__":
    main()
