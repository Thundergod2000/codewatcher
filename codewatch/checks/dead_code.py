"""Dead code detection using vulture."""

from __future__ import annotations
import os
import tempfile
from codewatch.types import CheckResult, Violation, Severity


def check_dead_code(filename: str, added_lines: list[str]) -> CheckResult:
    """
    Detect unused functions, classes, and variables in changed file.

    Uses vulture — reads from disk for full context.
    Only flags items defined in the added lines to avoid noise from
    pre-existing dead code that isn't part of this change.
    """
    try:
        import vulture as vulture_module
        from vulture import Vulture
    except ImportError:
        return CheckResult(
            check_name="dead_code",
            passed=True,
            skipped=True,
            skip_reason="vulture not installed — run: pip install vulture",
        )

    if not os.path.exists(filename):
        return CheckResult(
            check_name="dead_code",
            passed=True,
            skipped=True,
            skip_reason=f"{filename} not found on disk",
        )

    v = Vulture()
    try:
        v.scavenge([filename])
    except Exception as e:
        return CheckResult(
            check_name="dead_code",
            passed=True,
            skipped=True,
            skip_reason=f"vulture scan failed: {e}",
        )

    # Only flag items whose definition line appears in added lines
    added_line_numbers: set[int] = set()
    try:
        source_lines = open(filename).readlines()
        for i, source_line in enumerate(source_lines, start=1):
            stripped = source_line.strip()
            if any(stripped == added.strip() for added in added_lines if added.strip()):
                added_line_numbers.add(i)
    except (OSError, UnicodeDecodeError):
        pass

    violations: list[Violation] = []
    unused = v.get_unused_code(min_confidence=60)

    wanted = os.path.normcase(os.path.realpath(filename))
    for item in unused:
        found = os.path.normcase(os.path.realpath(item.filename))
        if found != wanted:
            continue
        # Warn on newly added dead code; skip pre-existing dead code
        if added_line_numbers and item.first_lineno not in added_line_numbers:
            continue
        violations.append(Violation(
            line=item.first_lineno,
            message=f"Unused {item.typ} '{item.name}' — remove it or add a usage",
            severity=Severity.WARNING,
        ))

    return CheckResult(
        check_name="dead_code",
        passed=True,  # dead code warns but never blocks
        violations=violations,
    )
