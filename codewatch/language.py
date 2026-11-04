"""Language detection and tree-sitter parsing utilities for JS/TS."""

from __future__ import annotations
import os
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Parser, Language


class LanguageType(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JSX = "jsx"
    TSX = "tsx"
    UNKNOWN = "unknown"


_EXTENSION_MAP: dict[str, LanguageType] = {
    ".py": LanguageType.PYTHON,
    ".js": LanguageType.JAVASCRIPT,
    ".jsx": LanguageType.JSX,
    ".ts": LanguageType.TYPESCRIPT,
    ".tsx": LanguageType.TSX,
}


def detect_language(filename: str) -> LanguageType:
    """Detect the language from file extension."""
    _, ext = os.path.splitext(filename)
    return _EXTENSION_MAP.get(ext.lower(), LanguageType.UNKNOWN)


def is_javascript_type(lang: LanguageType) -> bool:
    """Check if the language is JavaScript, JSX, TypeScript, or TSX."""
    return lang in (
        LanguageType.JAVASCRIPT,
        LanguageType.JSX,
        LanguageType.TYPESCRIPT,
        LanguageType.TSX,
    )


def is_python(lang: LanguageType) -> bool:
    """Check if the language is Python."""
    return lang == LanguageType.PYTHON


# Tree-sitter language instances (lazy-loaded, cached)
_LANGUAGE_CACHE: dict[str, Language] = {}
_GRAMMAR_ERRORS: dict[str, str] = {}

_GRAMMAR_PACKAGES = {
    "javascript": "tree-sitter-javascript",
    "typescript": "tree-sitter-typescript",
    "tsx": "tree-sitter-typescript",
}


def _load_grammar(grammar: str) -> Language | None:
    """Load a tree-sitter grammar by name. Returns None if unavailable."""
    if grammar in _LANGUAGE_CACHE:
        return _LANGUAGE_CACHE[grammar]

    try:
        from tree_sitter import Language
    except ImportError:
        _GRAMMAR_ERRORS[grammar] = "tree-sitter not installed — run: pip install tree-sitter"
        return None

    try:
        if grammar in ("javascript", "jsx"):
            # The JavaScript grammar understands JSX natively.
            import tree_sitter_javascript as tsjs
            language = Language(tsjs.language())
        elif grammar == "typescript":
            import tree_sitter_typescript as tsts
            language = Language(tsts.language_typescript())
        elif grammar == "tsx":
            import tree_sitter_typescript as tsts
            language = Language(tsts.language_tsx())
        else:
            _GRAMMAR_ERRORS[grammar] = f"unsupported grammar '{grammar}'"
            return None
    except ImportError:
        _GRAMMAR_ERRORS[grammar] = (
            f"tree-sitter grammar for {grammar} not installed — "
            f"run: pip install {_GRAMMAR_PACKAGES[grammar]}"
        )
        return None
    except (TypeError, ValueError, OSError) as e:
        _GRAMMAR_ERRORS[grammar] = f"could not load {grammar} grammar: {e}"
        return None

    _LANGUAGE_CACHE[grammar] = language
    return language


def _grammar_for(lang: LanguageType) -> str | None:
    if lang in (LanguageType.JAVASCRIPT, LanguageType.JSX):
        return "javascript"
    if lang == LanguageType.TYPESCRIPT:
        return "typescript"
    if lang == LanguageType.TSX:
        return "tsx"
    return None


def grammar_unavailable_reason(lang: LanguageType) -> str:
    """Return a human-readable reason the grammar is unavailable."""
    grammar = _grammar_for(lang)
    if grammar is None:
        return f"unsupported language: {lang.value}"
    return _GRAMMAR_ERRORS.get(
        grammar,
        f"could not parse {grammar} source with tree-sitter",
    )


def get_parser_for_language(lang: LanguageType) -> Parser | None:
    """Get a tree-sitter parser for the given language."""
    grammar = _grammar_for(lang)
    if grammar is None:
        return None

    language = _load_grammar(grammar)
    if language is None:
        return None

    try:
        from tree_sitter import Parser
    except ImportError:
        _GRAMMAR_ERRORS[grammar] = "tree-sitter not installed — run: pip install tree-sitter"
        return None

    return Parser(language)


def parse_source(source: str, lang: LanguageType):
    """Parse source code and return the tree-sitter tree, or None on failure."""
    parser = get_parser_for_language(lang)
    if parser is None:
        return None
    try:
        return parser.parse(bytes(source, "utf-8"))
    except (TypeError, ValueError, OSError):
        return None