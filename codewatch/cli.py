"""CLI entry point — codewatch scan --diff HEAD~1"""

from __future__ import annotations
import argparse
import os
import stat
import sys
from pathlib import Path

from dulwich.errors import NotGitRepository
from dulwich.repo import Repo

from codewatch.baseline import (
    BASELINE_FILENAME,
    BaselineError,
    collect_project_files,
    entries_from_results,
    load_baseline,
    write_baseline,
)
from codewatch.config import ConfigError, load_config
from codewatch.diff import (
    get_base_commit,
    get_blob_text,
    get_diff,
    parse_diff,
)
from codewatch.hook import run_hook
from codewatch.scanner import run_checks, should_block
from codewatch.reporter import (
    _ensure_utf8_output,
    print_results,
    print_stale_baseline,
)

_HOOK_MARKER = "# codewatch-managed"
_HOOK_BACKUP = "pre-push.codewatch-local"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codewatch",
        description="Offline code governance for Python, JavaScript, TypeScript, JSX and TSX — catches quality issues before they reach your repo",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # codewatch check — diff gate (committed/changed files only)
    check = sub.add_parser(
        "check", help="Scan committed/changed files before a push (default gate)"
    )
    check.add_argument(
        "--base",
        default=None,
        metavar="REF",
        help="Branch to diff against (default: HEAD~1)",
    )
    check.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    check.add_argument(
        "--no-block",
        action="store_true",
        help="Always exit 0, even on errors (useful in warn-only mode)",
    )

    # codewatch scan — whole-project health check
    scan = sub.add_parser(
        "scan", help="Scan the whole project for quality issues"
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

    # codewatch baseline write / update
    baseline = sub.add_parser(
        "baseline",
        help="Record accepted findings so only new issues are reported",
    )
    baseline_sub = baseline.add_subparsers(dest="baseline_action", required=True)
    for action, text in (
        ("write", "Write a new baseline file"),
        ("update", "Rewrite the baseline file from the current code"),
    ):
        write = baseline_sub.add_parser(action, help=text)
        write.add_argument(
            "--diff",
            default=None,
            metavar="REF",
            help="Baseline only this diff (default: whole project)",
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


def _collect_base_sources(
    base_sha: str | None,
    changed_files: dict[str, list[str]],
) -> dict[str, str]:
    """Read each changed file as it was at `base_sha`."""
    if not base_sha:
        return {}

    sources: dict[str, str] = {}
    for filename in changed_files:
        text = get_blob_text(base_sha, filename)
        if text is not None:
            sources[filename] = text
    return sources


def cmd_check(args: argparse.Namespace) -> int:
    """Diff-scanned gate over committed/changed files (pre-push behaviour)."""
    try:
        config = load_config()
        baseline = load_baseline()
    except (ConfigError, BaselineError) as exc:
        print(f"codewatch: {exc}", file=sys.stderr)
        return 2

    ref = f"{args.base}...HEAD" if args.base else "HEAD~1"
    raw_diff = get_diff(ref)

    if not raw_diff.strip():
        print("codewatch: no diff found — nothing to review")
        return 0

    changed_files = parse_diff(raw_diff)

    if not changed_files:
        print("codewatch: no supported files changed — nothing to review")
        return 0

    base_sources = _collect_base_sources(get_base_commit(ref), changed_files)
    results = run_checks(
        changed_files,
        config=config,
        baseline=baseline,
        base_sources=base_sources,
    )
    print_results(results, fmt=args.format, mode="check", files_scanned=len(results))
    print_stale_baseline(baseline.stale(set(changed_files)))

    if args.no_block:
        return 0

    return 1 if should_block(results) else 0


def cmd_scan(args: argparse.Namespace) -> int:
    """Whole-project health check."""
    try:
        config = load_config()
        baseline = load_baseline()
    except (ConfigError, BaselineError) as exc:
        print(f"codewatch: {exc}", file=sys.stderr)
        return 2

    changed_files = collect_project_files()

    if not changed_files:
        print("codewatch: no supported files found — nothing to scan")
        return 0

    results = run_checks(changed_files, config=config, baseline=baseline)
    print_results(
        results, fmt=args.format, mode="scan", files_scanned=len(results)
    )
    print_stale_baseline(baseline.stale(set(changed_files)))

    if args.no_block:
        return 0

    return 1 if should_block(results) else 0


def cmd_baseline(args: argparse.Namespace) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"codewatch: {exc}", file=sys.stderr)
        return 2

    if args.diff:
        try:
            raw_diff = get_diff(args.diff)
            changed_files = parse_diff(raw_diff)
        except Exception as exc:
            print(f"codewatch: could not read diff: {exc}", file=sys.stderr)
            return 2

        if not changed_files:
            print("codewatch: no supported files changed — nothing to baseline")
            return 0
    else:
        changed_files = collect_project_files()
        if not changed_files:
            print("codewatch: no supported files found — nothing to baseline")
            return 0

    try:
        results = run_checks(changed_files, config=config)
        entries = entries_from_results(results)
        existing = load_baseline()
        path = existing.path or (Path.cwd() / BASELINE_FILENAME)
        write_baseline(path, entries)
    except BaselineError as exc:
        print(f"codewatch: {exc}", file=sys.stderr)
        return 2

    print(f"✓  baseline written: {len(entries)} entry(ies) in {path}")
    print("   Review and commit this file. CI must never update it.")
    return 0


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

    if args.command == "check":
        sys.exit(cmd_check(args))
    elif args.command == "scan":
        sys.exit(cmd_scan(args))
    elif args.command == "baseline":
        sys.exit(cmd_baseline(args))
    elif args.command == "install-hook":
        sys.exit(cmd_install_hook(args))
    elif args.command == "hook":
        sys.exit(run_hook(sys.stdin.read()))


if __name__ == "__main__":
    main()
