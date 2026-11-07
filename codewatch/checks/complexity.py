"""Cyclomatic complexity check using radon."""

from __future__ import annotations
import os
from codewatch.diff import added_file_linenos
from codewatch.types import CheckResult, Violation, Severity, make_fingerprint

COMPLEXITY_THRESHOLD = 10  # warn above this, block above ERROR_THRESHOLD
ERROR_THRESHOLD = 20


def _complexity_by_name(cc_visit, source: str) -> dict[str, int]:
    """Map function name → highest cyclomatic complexity in `source`."""
    try:
        blocks = cc_visit(source)
    except SyntaxError:
        return {}

    scores: dict[str, int] = {}
    for block in blocks:
        scores[block.name] = max(scores.get(block.name, 0), block.complexity)
    return scores


def check_complexity(
    filename: str,
    added_lines: list[str],
    base_source: str | None = None,
) -> CheckResult:
    """
    Measure cyclomatic complexity of functions in the changed file.

    Uses radon — reads the file from disk so it gets full function context,
    not just the diff lines (complexity can't be measured on snippets).

    When `base_source` is supplied, a function over the error threshold only
    blocks if it is new or its complexity increased. Pre-existing debt warns.
    """
    try:
        from radon.complexity import cc_visit
    except ImportError:
        return CheckResult(
            check_name="complexity",
            passed=True,
            skipped=True,
            skip_reason="radon not installed — run: pip install radon",
        )

    if not added_lines:
        return CheckResult(check_name="complexity", passed=True)

    if not os.path.exists(filename):
        return CheckResult(
            check_name="complexity",
            passed=True,
            skipped=True,
            skip_reason=f"{filename} not found on disk (deleted or renamed)",
        )

    try:
        source = open(filename).read()
    except (OSError, UnicodeDecodeError) as e:
        return CheckResult(
            check_name="complexity",
            passed=True,
            skipped=True,
            skip_reason=f"could not read file: {e}",
        )

    violations: list[Violation] = []

    try:
        blocks = cc_visit(source)
    except SyntaxError:
        return CheckResult(
            check_name="complexity",
            passed=True,
            skipped=True,
            skip_reason="syntax error in file — fix syntax before complexity check",
        )

    added_nums = set(added_file_linenos(filename, added_lines))
    before = (
        _complexity_by_name(cc_visit, base_source)
        if base_source is not None
        else None
    )

    for block in blocks:
        end = getattr(block, "endline", block.lineno)
        if added_nums and not any(n in added_nums for n in range(block.lineno, end + 1)):
            continue

        complexity = block.complexity
        prior = before.get(block.name) if before is not None else None
        increased = before is None or prior is None or complexity > prior

        if complexity > ERROR_THRESHOLD and increased:
            rule_id = "CW-COMPLEX-001"
            violations.append(Violation(
                line=block.lineno,
                message=(
                    f"{block.name}() has cyclomatic complexity {complexity} "
                    f"(limit {ERROR_THRESHOLD}) — break it into smaller functions"
                ),
                severity=Severity.ERROR,
                rule_id=rule_id,
                fingerprint=make_fingerprint(rule_id, filename, block.name),
                detail=block.name,
                metric=complexity,
            ))
        elif complexity > COMPLEXITY_THRESHOLD:
            rule_id = "CW-COMPLEX-002"
            if complexity > ERROR_THRESHOLD:
                message = (
                    f"{block.name}() has pre-existing cyclomatic complexity "
                    f"{complexity} (limit {ERROR_THRESHOLD}) — not increased by this diff"
                )
            else:
                message = (
                    f"{block.name}() has cyclomatic complexity {complexity} "
                    f"(threshold {COMPLEXITY_THRESHOLD}) — consider simplifying"
                )
            violations.append(Violation(
                line=block.lineno,
                message=message,
                severity=Severity.WARNING,
                rule_id=rule_id,
                fingerprint=make_fingerprint(rule_id, filename, block.name),
                detail=block.name,
                metric=complexity,
            ))

    return CheckResult(
        check_name="complexity",
        passed=not any(v.severity == Severity.ERROR for v in violations),
        violations=violations,
    )
