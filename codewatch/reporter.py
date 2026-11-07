"""Format and print check results to the terminal."""

from __future__ import annotations
import json
import sys
from codewatch.types import CheckResult, Severity, SCHEMA_VERSION


def _ensure_utf8_output() -> None:
    """Force UTF-8 on stdout so check icons render on cp1252 Windows consoles."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except (ValueError, OSError):
        pass


def print_stale_baseline(entries) -> None:
    """Warn about baseline entries that no longer match a finding."""
    for entry in entries:
        print(
            f"codewatch: warning: stale baseline entry {entry.rule_id} "
            f"for {entry.file} — run: codewatch baseline update",
            file=sys.stderr,
        )


def _icon(passed: bool, has_warnings: bool) -> str:
    if not passed:
        return "✗"
    if has_warnings:
        return "⚠"
    return "✓"


def print_results(
    results: dict[str, list[CheckResult]],
    fmt: str = "text",
    mode: str = "check",
    files_scanned: int = 0,
) -> None:
    """
    Print all check results.

    fmt: "text" for human-readable terminal output, "json" for machine output.
    mode: scan mode label shown in the report header.
    files_scanned: number of files reviewed, shown in the report header.
    """
    _ensure_utf8_output()
    if fmt == "json":
        _print_json(results, mode=mode, files_scanned=files_scanned)
    else:
        _print_text(results, mode=mode, files_scanned=files_scanned)


def _print_text(
    results: dict[str, list[CheckResult]],
    mode: str = "check",
    files_scanned: int = 0,
) -> None:
    print(f"codewatch: {mode} — {files_scanned} file(s) scanned")

    totals = _accumulate_totals(results)
    for filename, file_results in results.items():
        _print_file_block(filename, file_results)

    _print_summary(totals, files_scanned)


def _accumulate_totals(
    results: dict[str, list[CheckResult]],
) -> dict[str, int]:
    total_violations = 0
    total_errors = 0
    files_with_issues = 0
    suppressed_by_reason: dict[str, int] = {}

    for file_results in results.values():
        for result in file_results:
            for reason, count in result.suppressed.items():
                suppressed_by_reason[reason] = (
                    suppressed_by_reason.get(reason, 0) + count
                )

        file_violations = [v for r in file_results for v in r.violations]
        file_errors = [v for v in file_violations if v.severity == Severity.ERROR]

        if file_violations:
            files_with_issues += 1

        total_violations += len(file_violations)
        total_errors += len(file_errors)

    return {
        "total_violations": total_violations,
        "total_errors": total_errors,
        "files_with_issues": files_with_issues,
        "suppressed_by_reason": suppressed_by_reason,
    }


def _print_file_block(
    filename: str, file_results: list[CheckResult]
) -> None:
    file_violations = [v for r in file_results for v in r.violations]
    file_errors = [v for v in file_violations if v.severity == Severity.ERROR]

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
            rule = f"  [{v.rule_id}]" if v.rule_id else ""
            print(f"              {badge_color}{badge}{reset} line {v.line}: {v.message}{rule}")


def _print_summary(totals: dict[str, int], files_scanned: int) -> None:
    print()
    suppressed_by_reason = totals["suppressed_by_reason"]
    if suppressed_by_reason:
        total_suppressed = sum(suppressed_by_reason.values())
        detail = ", ".join(
            f"{reason}: {count}"
            for reason, count in sorted(suppressed_by_reason.items())
        )
        print(f"   suppressed {total_suppressed} violation(s) ({detail})")

    total_errors = totals["total_errors"]
    total_violations = totals["total_violations"]
    files_with_issues = totals["files_with_issues"]

    if total_errors:
        print(
            f"\033[31m✗  {total_errors} error(s), {total_violations} total violation(s) "
            f"across {files_with_issues} file(s) — push blocked\033[0m"
        )
    elif total_violations:
        print(
            f"\033[33m⚠  {total_violations} warning(s) across {files_with_issues} "
            f"file(s) — push allowed\033[0m"
        )
    else:
        print(f"\033[32m✓  All checks passed ({files_scanned} file(s) reviewed)\033[0m")
    print()


def _print_json(
    results: dict[str, list[CheckResult]],
    mode: str = "check",
    files_scanned: int = 0,
) -> None:
    files = {}
    for filename, file_results in results.items():
        files[filename] = [
            {
                "check": r.check_name,
                "passed": r.passed,
                "skipped": r.skipped,
                "skip_reason": r.skip_reason,
                "suppressed": r.suppressed,
                "violations": [
                    {
                        "line": v.line,
                        "severity": v.severity.value,
                        "message": v.message,
                        "rule_id": v.rule_id,
                        "fingerprint": v.fingerprint,
                    }
                    for v in r.violations
                ],
            }
            for r in file_results
        ]
    output = {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "files_scanned": files_scanned,
        "files": files,
    }
    print(json.dumps(output, indent=2))


def _color(status: str) -> str:
    return {
        "PASS": "\033[32m",
        "WARN": "\033[33m",
        "FAIL": "\033[31m",
    }.get(status, "")
