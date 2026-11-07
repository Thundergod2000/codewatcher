"""Check that exported JavaScript/TypeScript functions and classes have JSDoc.

Policy: JSDoc is required for exported functions and classes (including
arrow-function/class-expression values assigned to exported declarations).
Private/internal declarations, type aliases, interfaces, enums, and class
methods are not flagged. TypeScript types do not exempt an export.
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

_FUNCTION_OR_CLASS_TYPES = {
    "function_declaration",
    "generator_function_declaration",
    "class_declaration",
    "abstract_class_declaration",
}

_FUNCTION_VALUE_TYPES = {
    "arrow_function",
    "function_expression",
    "generator_function",
    "class_expression",
}


def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", "replace")


def _has_jsdoc(source_lines: list[str], start_line: int) -> bool:
    """Return True if a /** ... */ block sits directly above start_line."""
    index = start_line - 2  # 0-based index of the line above
    while index >= 0:
        line = source_lines[index].strip()
        if not line:
            return False
        if line.startswith("@"):  # decorators sit between JSDoc and declaration
            index -= 1
            continue
        if line.endswith("*/"):
            cursor = index
            while cursor >= 0:
                candidate = source_lines[cursor].strip()
                if candidate.startswith("/**") or candidate.startswith("/*!"):
                    return True
                if candidate.startswith("/*"):
                    return False
                cursor -= 1
            return False
        return False
    return False


def _exported_names(tree, source_bytes: bytes) -> set[str]:
    """Names listed in `export { ... }` / `export { x as y }` clauses."""
    names: set[str] = set()

    def visit(node):
        if node.type == "export_statement":
            for child in node.children:
                if child.type == "export_clause":
                    for specifier in child.children:
                        if specifier.type == "export_specifier":
                            name_node = specifier.child_by_field_name("name")
                            if name_node is None and specifier.children:
                                name_node = specifier.children[0]
                            if name_node is not None:
                                names.add(_node_text(name_node, source_bytes))
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return names


def _is_exported(node) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type == "export_statement":
            return True
        parent = parent.parent
    return False


def _declaration_name(node, source_bytes: bytes) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return _node_text(name_node, source_bytes)

    for child in node.children:
        if child.type in ("identifier", "type_identifier"):
            return _node_text(child, source_bytes)
    return None


def _is_documented_declaration(node) -> bool:
    """Only functions and classes (directly or as exported values) qualify."""
    if node.type in _FUNCTION_OR_CLASS_TYPES:
        return True
    if node.type == "variable_declarator":
        value = node.child_by_field_name("value")
        return value is not None and value.type in _FUNCTION_VALUE_TYPES
    return False


def _kind_for(node) -> str:
    if node.type == "variable_declarator":
        return "function"
    if node.type in ("class_declaration", "abstract_class_declaration"):
        return "class"
    return "function"


def _doc_anchor_line(node) -> int:
    """Return the line where the JSDoc block should start (above decorators)."""
    anchor = node.start_point[0] + 1

    for child in node.children:
        if child.type == "decorator":
            anchor = min(anchor, child.start_point[0] + 1)

    parent = node.parent
    while parent is not None:
        if parent.type == "export_statement":
            for child in parent.children:
                if child.type == "decorator":
                    anchor = min(anchor, child.start_point[0] + 1)
            break
        parent = parent.parent

    return anchor


def _is_component_name(name: str | None) -> bool:
    """React components are capitalized declarations."""
    return bool(name) and name[:1].isupper()


def check_js_docstrings(
    filename: str,
    added_lines: list[str],
    require_exports: bool = True,
    require_components: bool = True,
) -> CheckResult:
    """
    Detect exported JS/TS functions and classes in added lines lacking JSDoc.

    Reads the full file for accurate parsing but only flags declarations
    whose definition line appears in the diff.

    `require_exports` requires JSDoc on exported APIs (default true).
    `require_components` requires JSDoc on capitalized React components
    (default true).
    """
    if not os.path.exists(filename):
        return CheckResult(
            check_name="docstrings",
            passed=True,
            skipped=True,
            skip_reason=f"{filename} not found on disk",
        )

    try:
        source = open(filename, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as e:
        return CheckResult(
            check_name="docstrings",
            passed=True,
            skipped=True,
            skip_reason=f"could not read file: {e}",
        )

    lang = detect_language(filename)
    if not is_javascript_type(lang):
        return CheckResult(
            check_name="docstrings",
            passed=True,
            skipped=True,
            skip_reason="not a JavaScript/TypeScript file",
        )

    tree = parse_source(source, lang)
    if tree is None:
        return CheckResult(
            check_name="docstrings",
            passed=True,
            skipped=True,
            skip_reason=grammar_unavailable_reason(lang),
        )

    if tree.root_node.has_error:
        return CheckResult(
            check_name="docstrings",
            passed=True,
            skipped=True,
            skip_reason="syntax error — fix before JSDoc check",
        )

    source_bytes = source.encode("utf-8")
    source_lines = source.splitlines()
    added_nums = set(added_file_linenos(filename, added_lines)) if added_lines else set()
    exported_names = _exported_names(tree, source_bytes)

    violations: list[Violation] = []

    def visit(node):
        if _is_documented_declaration(node):
            name = _declaration_name(node, source_bytes)
            is_public = _is_exported(node) or (name is not None and name in exported_names)
            if is_public and name is not None:
                should_require = require_exports
                if _is_component_name(name):
                    should_require = should_require and require_components
                if should_require:
                    start_line = node.start_point[0] + 1
                    in_diff = not added_nums or start_line in added_nums
                    if in_diff and not _has_jsdoc(source_lines, _doc_anchor_line(node)):
                        violations.append(Violation(
                            line=start_line,
                            message=(
                                f"Exported {_kind_for(node)} '{name}' has no JSDoc comment — "
                                f"add a description for API documentation"
                            ),
                            severity=Severity.WARNING,
                            rule_id="CW-DOC-001",
                            fingerprint=make_fingerprint("CW-DOC-001", filename, name),
                            detail=name,
                        ))

        for child in node.children:
            visit(child)

    visit(tree.root_node)

    return CheckResult(
        check_name="docstrings",
        passed=True,  # missing JSDoc warns, never blocks
        violations=violations,
    )