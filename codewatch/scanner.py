"""Orchestrates all checks across changed files."""

from __future__ import annotations
from codewatch.baseline import Baseline
from codewatch.config import Config, load_config
from codewatch.suppress import apply_suppressions
from codewatch.diff import is_ignored_path
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


def _run_python_checks(
    filename: str,
    added_lines: list[str],
    base_source: str | None = None,
) -> list[CheckResult]:
    """Run all Python checks on a file."""
    return [
        check_secrets(filename, added_lines),
        check_complexity(filename, added_lines, base_source=base_source),
        check_dead_code(filename, added_lines),
        check_test_presence(filename, added_lines),
        check_docstrings(filename, added_lines),
    ]


def _run_js_checks(
    filename: str,
    added_lines: list[str],
    base_source: str | None = None,
) -> list[CheckResult]:
    """Run all JavaScript/TypeScript checks on a file."""
    return [
        check_js_secrets(filename, added_lines),
        check_js_complexity(filename, added_lines, base_source=base_source),
        check_js_dead_code(filename, added_lines),
        check_js_test_presence(filename, added_lines),
        check_js_docstrings(filename, added_lines),
    ]


def run_checks(
    changed_files: dict[str, list[str]],
    config: Config | None = None,
    baseline: Baseline | None = None,
    base_sources: dict[str, str] | None = None,
) -> dict[str, list[CheckResult]]:
    """
    Run all checks on each changed file, then apply suppressions.

    Args:
        changed_files: mapping of filename → list of added lines (from diff parser)
        config: allowlist config; loaded from codewatch.yaml when omitted
        baseline: accepted-findings baseline; no baseline filtering when omitted
        base_sources: filename → file text before the change, for complexity delta

    Returns:
        mapping of filename → list of CheckResult (one per check)
    """
    if config is None:
        config = load_config()

    results: dict[str, list[CheckResult]] = {}

    for filename, added_lines in changed_files.items():
        if is_ignored_path(filename):
            continue

        lang = detect_language(filename)
        base_source = (base_sources or {}).get(filename)

        if is_python(lang):
            file_results = _run_python_checks(
                filename, added_lines, base_source=base_source
            )
        elif is_javascript_type(lang):
            file_results = _run_js_checks(
                filename, added_lines, base_source=base_source
            )
        else:
            # Unknown language - skip
            continue

        file_results = apply_suppressions(filename, file_results, config)
        if baseline is not None:
            file_results = baseline.apply(filename, file_results)
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
