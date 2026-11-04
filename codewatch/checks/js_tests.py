"""Check that changed JavaScript/TypeScript source files have corresponding test files."""

from __future__ import annotations
import os
from codewatch.types import CheckResult, Violation, Severity

# Test file patterns
_TEST_PATTERNS = [
    "test_{stem}.{ext}",
    "{stem}.test.{ext}",
    "{stem}.spec.{ext}",
    "__tests__/{stem}.test.{ext}",
    "__tests__/{stem}.spec.{ext}",
]

# Test directories
_TEST_DIRS = [
    "tests",
    "test",
    "__tests__",
    "src/tests",
    "src/__tests__",
]


def _find_test_file(filename: str) -> str | None:
    """
    Search for a test file matching the given source file.

    Looks for common JS/TS test naming patterns in common test directories.
    """
    basename = os.path.basename(filename)
    stem = os.path.splitext(basename)[0]
    ext = os.path.splitext(basename)[1][1:]  # without dot

    # Determine test extensions based on source extension
    # .ts/.tsx files can have .ts/.tsx tests
    # .js/.jsx files can have .js/.jsx tests
    if ext in ("ts", "tsx"):
        test_exts = ["ts", "tsx"]
    else:
        test_exts = ["js", "jsx"]

    candidates = []
    for test_ext in test_exts:
        for pattern in _TEST_PATTERNS:
            candidates.append(pattern.format(stem=stem, ext=test_ext))

    # Also check alongside the source file itself
    source_dir = os.path.dirname(filename)

    for test_dir in _TEST_DIRS + [source_dir]:
        for candidate in candidates:
            path = os.path.join(test_dir, candidate)
            if os.path.exists(path):
                return path

    return None


def _is_test_file(filename: str) -> bool:
    """Check if a file is a test file based on naming conventions."""
    basename = os.path.basename(filename)
    stem = os.path.splitext(basename)[0]

    # Check for test patterns
    if stem.startswith("test_"):
        return True
    if stem.endswith(".test") or stem.endswith(".spec"):
        return True
    if "__tests__" in filename:
        return True
    if basename in ("jest.config.js", "jest.config.ts", "vitest.config.ts", "vitest.config.js"):
        return True

    return False


def check_js_test_presence(filename: str, added_lines: list[str]) -> CheckResult:
    """
    Warn when a changed JS/TS source file has no matching test file.

    Skips files that are themselves test files, config files, or type definitions.
    """
    basename = os.path.basename(filename)

    # Skip test files, config files, and type definitions
    if (
        _is_test_file(filename)
        or basename.endswith(".d.ts")
        or basename in ("jest.config.js", "jest.config.ts", "vitest.config.ts", "vitest.config.js")
        or "node_modules" in filename
    ):
        return CheckResult(
            check_name="test_presence",
            passed=True,
            skipped=True,
            skip_reason="file is a test, config, or type definition — skipping",
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
                    f"No test file found for {basename} — expected "
                    f"{os.path.splitext(basename)[0]}.test.{os.path.splitext(basename)[1][1:]} "
                    f"or __tests__/ variant"
                ),
                severity=Severity.WARNING,
            )
        ],
    )