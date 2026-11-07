"""Cyclomatic complexity check for JavaScript/TypeScript using tree-sitter.

Metric: base score of 1 per function, plus one for each `if`, `for`,
`for-in`/`for-of`, `while`, `do-while`, `catch`, `case`, ternary (`?:`),
and each `&&` / `||` operator. Nested functions are scored separately.

The metric closely mirrors radon's cyclomatic complexity used for Python,
so the existing warn/block thresholds apply unchanged.
"""

from __future__ import annotations
import os
from codewatch.diff import added_file_linenos
from codewatch.language import (
    detect_language,
    grammar_unavailable_reason,
    is_javascript_type,
    parse_source,
)
from codewatch.types import CheckResult, Violation, Severity, make_fingerprint

COMPLEXITY_THRESHOLD = 10  # warn above this
ERROR_THRESHOLD = 20       # block above this

_FUNCTION_TYPES = {
    "function_declaration",
    "generator_function_declaration",
    "function_expression",
    "generator_function",
    "arrow_function",
    "method_definition",
}

_DECISION_TYPES = {
    "if_statement",
    "for_statement",
    "for_in_statement",
    "while_statement",
    "do_statement",
    "catch_clause",
    "switch_case",
    "ternary_expression",
}

_LOGICAL_OPERATORS = {"&&", "||", "??"}


def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", "replace")


def _function_name(node, source_bytes: bytes) -> str:
    """Extract a readable function name from a function-like node."""
    if node.type == "method_definition":
        for child in node.children:
            if child.type in ("property_identifier", "identifier", "private_property_identifier"):
                return _node_text(child, source_bytes)

    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return _node_text(name_node, source_bytes)

    # Arrow/function expressions assigned to a variable take the variable name.
    parent = node.parent
    if parent is not None and parent.type == "variable_declarator":
        name_node = parent.child_by_field_name("name")
        if name_node is not None and name_node.type == "identifier":
            return _node_text(name_node, source_bytes)

    return "<anonymous>"


def _calculate_complexity(node) -> int:
    """Calculate cyclomatic complexity for one function node."""
    score = 1

    def walk(current):
        nonlocal score
        # Nested functions are measured on their own, not folded into the parent.
        if current is not node and current.type in _FUNCTION_TYPES:
            return

        if current.type in _DECISION_TYPES:
            score += 1
        elif current.type in _LOGICAL_OPERATORS:
            score += 1

        for child in current.children:
            walk(child)

    walk(node)
    return score


def _base_complexity(base_source: str, lang: str) -> dict[str, int] | None:
    """Map function name → highest cyclomatic complexity in the base file."""
    tree = parse_source(base_source, lang)
    if tree is None or tree.root_node.has_error:
        return None

    source_bytes = base_source.encode("utf-8")
    scores: dict[str, int] = {}

    def visit(node):
        if node.type in _FUNCTION_TYPES:
            name = _function_name(node, source_bytes)
            score = _calculate_complexity(node)
            scores[name] = max(scores.get(name, 0), score)

        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return scores


def check_js_complexity(
    filename: str,
    added_lines: list[str],
    base_source: str | None = None,
) -> CheckResult:
    """
    Measure cyclomatic complexity of functions in the changed JS/TS file.

    Uses tree-sitter — reads the file from disk for full function context.
    Only reports functions that intersect with added lines.

    When `base_source` is supplied, a function over the error threshold only
    blocks if it is new or its complexity increased. Pre-existing debt warns.
    """
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
        source = open(filename, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as e:
        return CheckResult(
            check_name="complexity",
            passed=True,
            skipped=True,
            skip_reason=f"could not read file: {e}",
        )

    lang = detect_language(filename)
    if not is_javascript_type(lang):
        return CheckResult(
            check_name="complexity",
            passed=True,
            skipped=True,
            skip_reason="not a JavaScript/TypeScript file",
        )

    tree = parse_source(source, lang)
    if tree is None:
        return CheckResult(
            check_name="complexity",
            passed=True,
            skipped=True,
            skip_reason=grammar_unavailable_reason(lang),
        )

    if tree.root_node.has_error:
        return CheckResult(
            check_name="complexity",
            passed=True,
            skipped=True,
            skip_reason="syntax error in file — fix syntax before complexity check",
        )

    violations: list[Violation] = []
    source_bytes = source.encode("utf-8")
    added_nums = set(added_file_linenos(filename, added_lines))
    before = (
        _base_complexity(base_source, lang)
        if base_source is not None
        else None
    )

    def visit(node):
        if node.type in _FUNCTION_TYPES:
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1

            if added_nums and not any(n in added_nums for n in range(start_line, end_line + 1)):
                # Function untouched by the diff - still visit nested functions.
                for child in node.children:
                    visit(child)
                return

            complexity = _calculate_complexity(node)
            name = _function_name(node, source_bytes)
            prior = (
                before.get(name)
                if before is not None and name != "<anonymous>"
                else None
            )
            increased = before is None or prior is None or complexity > prior

            if complexity > ERROR_THRESHOLD and increased:
                rule_id = "CW-COMPLEX-001"
                violations.append(Violation(
                    line=start_line,
                    message=(
                        f"{name}() has cyclomatic complexity {complexity} "
                        f"(limit {ERROR_THRESHOLD}) — break it into smaller functions"
                    ),
                    severity=Severity.ERROR,
                    rule_id=rule_id,
                    fingerprint=make_fingerprint(rule_id, filename, name),
                    detail=name,
                    metric=complexity,
                ))
            elif complexity > COMPLEXITY_THRESHOLD:
                rule_id = "CW-COMPLEX-002"
                if complexity > ERROR_THRESHOLD:
                    message = (
                        f"{name}() has pre-existing cyclomatic complexity "
                        f"{complexity} (limit {ERROR_THRESHOLD}) — not increased by this diff"
                    )
                else:
                    message = (
                        f"{name}() has cyclomatic complexity {complexity} "
                        f"(threshold {COMPLEXITY_THRESHOLD}) — consider simplifying"
                    )
                violations.append(Violation(
                    line=start_line,
                    message=message,
                    severity=Severity.WARNING,
                    rule_id=rule_id,
                    fingerprint=make_fingerprint(rule_id, filename, name),
                    detail=name,
                    metric=complexity,
                ))

        for child in node.children:
            visit(child)

    visit(tree.root_node)

    return CheckResult(
        check_name="complexity",
        passed=not any(v.severity == Severity.ERROR for v in violations),
        violations=violations,
    )