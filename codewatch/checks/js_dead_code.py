"""Dead code detection for JavaScript/TypeScript using tree-sitter.

Conservative by design: only warns about newly added declarations that are
not exported, not React components (capitalised names), and whose name never
appears anywhere else in the file. Exports and conventionally discovered
components are treated as intentionally used.
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

_DECLARATION_TYPES = {
    "function_declaration",
    "generator_function_declaration",
    "class_declaration",
    "abstract_class_declaration",
    "variable_declarator",
}

_USAGE_IDENTIFIER_TYPES = {
    "identifier",
    "shorthand_property_identifier",
    "type_identifier",
}


def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", "replace")


def _declaration_name(node, source_bytes: bytes) -> str | None:
    """Return the declared name, or None for destructuring patterns."""
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        if name_node.type in ("identifier", "type_identifier"):
            return _node_text(name_node, source_bytes)
        return None  # object_pattern / array_pattern: not confidently nameable

    for child in node.children:
        if child.type in ("identifier", "type_identifier"):
            return _node_text(child, source_bytes)
    return None


def _is_exported(node) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type == "export_statement":
            return True
        parent = parent.parent
    return False


def _exported_names(tree, source_bytes: bytes) -> set[str]:
    """Names listed in `export { ... }` clauses."""
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


def check_js_dead_code(filename: str, added_lines: list[str]) -> CheckResult:
    """
    Detect unused declarations in changed JS/TS file.

    Uses tree-sitter — reads from disk for full context.
    Only flags declarations defined in the added lines to avoid noise from
    pre-existing dead code that isn't part of this change.
    """
    if not os.path.exists(filename):
        return CheckResult(
            check_name="dead_code",
            passed=True,
            skipped=True,
            skip_reason=f"{filename} not found on disk",
        )

    try:
        source = open(filename, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError) as e:
        return CheckResult(
            check_name="dead_code",
            passed=True,
            skipped=True,
            skip_reason=f"could not read file: {e}",
        )

    lang = detect_language(filename)
    if not is_javascript_type(lang):
        return CheckResult(
            check_name="dead_code",
            passed=True,
            skipped=True,
            skip_reason="not a JavaScript/TypeScript file",
        )

    tree = parse_source(source, lang)
    if tree is None:
        return CheckResult(
            check_name="dead_code",
            passed=True,
            skipped=True,
            skip_reason=grammar_unavailable_reason(lang),
        )

    if tree.root_node.has_error:
        return CheckResult(
            check_name="dead_code",
            passed=True,
            skipped=True,
            skip_reason="syntax error in file — fix syntax before dead code check",
        )

    source_bytes = source.encode("utf-8")

    # Build the set of line numbers added by the diff.
    added_line_numbers = set(added_file_linenos(filename, added_lines)) if added_lines else set()

    exported_names = _exported_names(tree, source_bytes)

    declarations: list[tuple[int, str, str]] = []  # (line, name, kind)
    name_ranges: set[tuple[int, int]] = set()
    usage_names: set[str] = set()

    def collect(node):
        if node.type in _DECLARATION_TYPES:
            name = _declaration_name(node, source_bytes)
            if name is not None and not _is_exported(node) and name not in exported_names:
                declarations.append((node.start_point[0] + 1, name, node.type))
                for child in node.children:
                    if child.type in ("identifier", "type_identifier") and _node_text(child, source_bytes) == name:
                        name_ranges.add((child.start_byte, child.end_byte))
                        break

        elif node.type in _USAGE_IDENTIFIER_TYPES:
            usage_names.add(_node_text(node, source_bytes))

        for child in node.children:
            collect(child)

    collect(tree.root_node)

    violations: list[Violation] = []

    for line, name, kind in declarations:
        if added_line_numbers and line not in added_line_numbers:
            continue

        # Exported declarations and capitalised component names are public API.
        if name[0].isupper():
            continue

        # The declaration name itself is collected as an identifier usage.
        # Count remaining occurrences to decide if it is used elsewhere.
        if name in usage_names:
            occurrences = sum(
                1 for node, text in _iter_identifiers(tree, source_bytes)
                if text == name and (node.start_byte, node.end_byte) not in name_ranges
            )
            if occurrences > 0:
                continue

        label = kind.replace("_", " ")
        violations.append(Violation(
            line=line,
            message=f"Unused {label} '{name}' — remove it or add a usage",
            severity=Severity.WARNING,
            rule_id="CW-DEAD-001",
            fingerprint=make_fingerprint("CW-DEAD-001", filename, name),
            detail=name,
        ))

    return CheckResult(
        check_name="dead_code",
        passed=True,  # dead code warns but never blocks
        violations=violations,
    )


def _iter_identifiers(tree, source_bytes: bytes):
    def visit(node):
        if node.type in _USAGE_IDENTIFIER_TYPES:
            yield node, _node_text(node, source_bytes)
        for child in node.children:
            yield from visit(child)

    yield from visit(tree.root_node)