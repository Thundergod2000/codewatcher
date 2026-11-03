"""Format and print check results to the terminal."""

from __future__ import annotations
import json
import sys
from codewatch.types import CheckResult, Severity


def _ensure_utf8_output() -> None:
    """Force UTF-8 on stdout so check icons render on cp1252 Windows consoles."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except (ValueError, OSError):
        pass


def _icon(passed: bool, has_warnings: bool) -> str:
    if not passed:
        return "✗"
    if has_warnings:
        return "⚠"
    return "✓"


def print_results(results: dict[str, list[CheckResult]], fmt: str = "text") -> None:
    """
    Print all check results.

    fmt: "text" for human-readable terminal output, "json" for machine output.
    """
    _ensure_utf8_output()
    if fmt == "json":
        _print_json(results)
    else:
        _print_text(results)


def _print_text(results: dict[str, list[CheckResult]]) -> None:
    total_violations = 0
    total_errors = 0
    files_with_issues = 0

    for filename, file_results in results.items():
        file_violations = [v for r in file_results for v in r.violations]
        file_errors = [v for v in file_violations if v.severity == Severity.ERROR]

        if file_violations:
            files_with_issues += 1

        total_violations += len(file_violations)
        total_errors += len(file_errors)

        # File header
        has_errors = bool(file_errors)
        has_warnings = bool(file_violations) and not has_errors
        status = "FAIL" if has_errors else ("WARN" if has_warnings else "PASS")
        color = _color(status)
        reset = "\033[0m"

        print(f"\n{color}{status}{reset}  {filename}")

        for result in file_results:
            if result.skipped:
                print(f"       skip  [{result.check_name}] {result.skip_reason}")
                continue

            check_icon = _icon(result.passed, bool(result.violations))
            check_color = "\033[31m" if not result.passed else ("\033[33m" if result.violations else "\033[32m")
            print(f"       {check_color}{check_icon}{reset}  {result.check_name}")

            for v in result.violations:
                badge = "ERROR  " if v.severity == Severity.ERROR else "warn   "
                badge_color = "\033[31m" if v.severity == Severity.ERROR else "\033[33m"
                print(f"              {badge_color}{badge}{reset} line {v.line}: {v.message}")

    # Summary line
    print()
    if total_errors:
        print(f"\033[31m✗  {total_errors} error(s), {total_violations} total violation(s) across {files_with_issues} file(s) — push blocked\033[0m")
    elif total_violations:
        print(f"\033[33m⚠  {total_violations} warning(s) across {files_with_issues} file(s) — push allowed\033[0m")
    else:
        checked = len(results)
        print(f"\033[32m✓  All checks passed ({checked} file(s) reviewed)\033[0m")
    print()


def _print_json(results: dict[str, list[CheckResult]]) -> None:
    output = {}
    for filename, file_results in results.items():
        output[filename] = [
            {
                "check": r.check_name,
                "passed": r.passed,
                "skipped": r.skipped,
                "skip_reason": r.skip_reason,
                "violations": [
                    {
                        "line": v.line,
                        "severity": v.severity.value,
                        "message": v.message,
                    }
                    for v in r.violations
                ],
            }
            for r in file_results
        ]
    print(json.dumps(output, indent=2))


def _color(status: str) -> str:
    return {
        "PASS": "\033[32m",
        "WARN": "\033[33m",
        "FAIL": "\033[31m",
    }.get(status, "")
