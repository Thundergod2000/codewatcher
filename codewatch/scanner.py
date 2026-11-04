"""Orchestrates all checks across changed files."""

from __future__ import annotations
from codewatch.types import CheckResult, Severity
from codewatch.language import detect_language, is_javascript_type, is_python
from codewatch.checks import (
    check_complexity,
    check_dead_code,
    check_secrets,
    check_test_presence,
    check_docstrings,
    check_js_secrets,
    check_js_complexity,
    check_js_dead_code,
    check_js_test_presence,
    check_js_docstrings,
)


def _run_python_checks(filename: str, added_lines: list[str]) -> list[CheckResult]:
    """Run all Python checks on a file."""
    return [
        check_secrets(filename, added_lines),
        check_complexity(filename, added_lines),
        check_dead_code(filename, added_lines),
        check_test_presence(filename, added_lines),
        check_docstrings(filename, added_lines),
    ]


def _run_js_checks(filename: str, added_lines: list[str]) -> list[CheckResult]:
    """Run all JavaScript/TypeScript checks on a file."""
    return [
        check_js_secrets(filename, added_lines),
        check_js_complexity(filename, added_lines),
        check_js_dead_code(filename, added_lines),
        check_js_test_presence(filename, added_lines),
        check_js_docstrings(filename, added_lines),
    ]


def run_checks(changed_files: dict[str, list[str]]) -> dict[str, list[CheckResult]]:
    """
    Run all checks on each changed file.

    Args:
        changed_files: mapping of filename → list of added lines (from diff parser)

    Returns:
        mapping of filename → list of CheckResult (one per check)
    """
    results: dict[str, list[CheckResult]] = {}

    for filename, added_lines in changed_files.items():
        lang = detect_language(filename)

        if is_python(lang):
            file_results = _run_python_checks(filename, added_lines)
        elif is_javascript_type(lang):
            file_results = _run_js_checks(filename, added_lines)
        else:
            # Unknown language - skip
            continue

        results[filename] = file_results

    return results


def should_block(results: dict[str, list[CheckResult]]) -> bool:
    """Return True if any check produced an ERROR-level violation."""
    for file_results in results.values():
        for result in file_results:
            for violation in result.violations:
                if violation.severity == Severity.ERROR:
                    return True
    return False
