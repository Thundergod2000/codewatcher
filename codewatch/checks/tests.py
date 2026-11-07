"""Check that changed source files have a corresponding test file."""

from __future__ import annotations
import os
from codewatch.types import CheckResult, Violation, Severity, make_fingerprint

# Folders where test files might live, relative to repo root
_TEST_DIRS = ["tests", "test", "src/tests"]


def _find_test_file(filename: str) -> str | None:
    """
    Search for a test file matching the given source file.

    Looks for test_<name>.py or <name>_test.py in common test directories.
    """
    basename = os.path.basename(filename)           # e.g. scanner.py
    stem = os.path.splitext(basename)[0]            # e.g. scanner

    candidates = [
        f"test_{stem}.py",
        f"{stem}_test.py",
    ]

    # Also check alongside the source file itself
    source_dir = os.path.dirname(filename)

    for test_dir in _TEST_DIRS + [source_dir]:
        for candidate in candidates:
            path = os.path.join(test_dir, candidate)
            if os.path.exists(path):
                return path

    return None


def check_test_presence(filename: str, added_lines: list[str]) -> CheckResult:
    """
    Warn when a changed source file has no matching test file.

    Skips files that are themselves test files, __init__.py, or config files.
    """
    basename = os.path.basename(filename)

    # Skip test files, inits, and setup files
    if (
        basename.startswith("test_")
        or basename.endswith("_test.py")
        or basename in ("__init__.py", "setup.py", "conftest.py")
        or "migrations" in filename
    ):
        return CheckResult(
            check_name="test_presence",
            passed=True,
            skipped=True,
            skip_reason="file is a test, init, or config — skipping",
        )

    test_file = _find_test_file(filename)

    if test_file:
        return CheckResult(check_name="test_presence", passed=True)

    return CheckResult(
        check_name="test_presence",
        passed=True,  # warns only — missing tests don't block
        violations=[
            Violation(
                line=1,
                message=(
                    f"No test file found for {basename} — "
                    f"expected test_{os.path.splitext(basename)[0]}.py in tests/"
                ),
                severity=Severity.WARNING,
                rule_id="CW-TEST-001",
                fingerprint=make_fingerprint("CW-TEST-001", filename, filename),
            )
        ],
    )
