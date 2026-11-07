"""Check that public functions and classes have docstrings."""

from __future__ import annotations
import ast
import os
from codewatch.types import CheckResult, Violation, Severity, make_fingerprint


def _is_public(name: str) -> bool:
    """Return True if the name is considered public (not prefixed with _)."""
    return not name.startswith("_")


def check_docstrings(filename: str, added_lines: list[str]) -> CheckResult:
    """
    Detect public functions and classes in added lines that lack docstrings.

    Reads the full file for accurate AST parsing but only flags items
    whose definition line appears in the diff.
    """
    if not os.path.exists(filename):
        return CheckResult(
            check_name="docstrings",
            passed=True,
            skipped=True,
            skip_reason=f"{filename} not found on disk",
        )

    try:
        source = open(filename).read()
    except (OSError, UnicodeDecodeError) as e:
        return CheckResult(
            check_name="docstrings",
            passed=True,
            skipped=True,
            skip_reason=f"could not read file: {e}",
        )

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return CheckResult(
            check_name="docstrings",
            passed=True,
            skipped=True,
            skip_reason="syntax error — fix before docstring check",
        )

    # Build set of line numbers present in the diff (rough match on content)
    source_lines = source.splitlines()
    added_set = {line.strip() for line in added_lines if line.strip()}

    def line_is_in_diff(lineno: int) -> bool:
        if not added_set:
            return True  # if we can't tell, check everything
        idx = lineno - 1
        if 0 <= idx < len(source_lines):
            return source_lines[idx].strip() in added_set
        return False

    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if not _is_public(node.name):
            continue
        if not line_is_in_diff(node.lineno):
            continue

        has_docstring = (
            isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ) if node.body else False

        if not has_docstring:
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            violations.append(Violation(
                line=node.lineno,
                message=(
                    f"Public {kind} '{node.name}' has no docstring — "
                    f"add a one-line description of what it does"
                ),
                severity=Severity.WARNING,
                rule_id="CW-DOC-001",
                fingerprint=make_fingerprint("CW-DOC-001", filename, node.name),
                detail=node.name,
            ))

    return CheckResult(
        check_name="docstrings",
        passed=True,  # missing docstrings warn, never block
        violations=violations,
    )
