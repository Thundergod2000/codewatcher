"""CLI entry point — codewatch scan --diff HEAD~1"""

from __future__ import annotations
import argparse
import sys
from codewatch.diff import get_diff, parse_diff
from codewatch.scanner import run_checks, should_block
from codewatch.reporter import print_results


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
    hook = sub.add_parser("install-hook", help="Install pre-push git hook in current repo")
    hook.add_argument(
        "--ref",
        default="HEAD~1",
        help="Git ref the hook will diff against (default: HEAD~1)",
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


def cmd_install_hook(args: argparse.Namespace) -> int:
    import os
    import stat

    hook_dir = os.path.join(".git", "hooks")
    if not os.path.isdir(hook_dir):
        print("codewatch: .git/hooks not found — are you in a git repo?")
        return 1

    hook_path = os.path.join(hook_dir, "pre-push")
    # Diff the commits being pushed (remote SHA...local SHA), not HEAD~1.
    # --ref is the fallback when stdin has no SHAs (manual test / missing remote).
    hook_content = f"""#!/bin/sh
# Installed by codewatch-lite
echo "codewatch: reviewing changes..."
z40=0000000000000000000000000000000000000000
blocked=0
reviewed=0
while read local_ref local_sha remote_ref remote_sha
do
  if [ "$local_sha" = "$z40" ]; then
    continue
  fi
  if [ "$remote_sha" = "$z40" ]; then
    range="{args.ref}...$local_sha"
  else
    range="$remote_sha...$local_sha"
  fi
  codewatch scan --diff "$range" || blocked=1
  reviewed=1
done
if [ "$reviewed" -eq 0 ]; then
  codewatch scan --diff {args.ref} || blocked=1
fi
exit $blocked
"""
    with open(hook_path, "w", newline="\n") as f:
        f.write(hook_content)

    # Make executable
    current = os.stat(hook_path).st_mode
    os.chmod(hook_path, current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"✓  pre-push hook installed at {hook_path}")
    print("   Every push will now be reviewed by codewatch.")
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "scan":
        sys.exit(cmd_scan(args))
    elif args.command == "install-hook":
        sys.exit(cmd_install_hook(args))


if __name__ == "__main__":
    main()
