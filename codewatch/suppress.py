"""Inline ignore directives and violation suppression."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from codewatch.config import Config
from codewatch.types import CheckResult, Severity

_DIRECTIVE = re.compile(
    r"codewatch:\s*ignore(?P<scope>-next-line|-file)?(?P<rest>.*)$",
    re.IGNORECASE,
)
_RULE_ID = re.compile(r"CW-[A-Z]+-\d{3}")


@dataclass
class InlineIgnores:
    """Ignore directives found in one file."""

    file_all: bool = False
    file_rules: set[str] = field(default_factory=set)
    lines: dict[int, set[str] | None] = field(default_factory=dict)

    def ignores(self, lineno: int, rule_id: str) -> bool:
        if self.file_all or rule_id in self.file_rules:
            return True
        if lineno not in self.lines:
            return False
        rules = self.lines[lineno]
        return rules is None or not rules or rule_id in rules


def parse_inline_ignores(source: str) -> InlineIgnores:
    """Parse `# codewatch: ignore` directives from source text."""
    result = InlineIgnores()

    for index, line in enumerate(source.splitlines(), start=1):
        match = _DIRECTIVE.search(line)
        if match is None:
            continue

        scope = match.group("scope") or ""
        rules = set(_RULE_ID.findall(match.group("rest") or ""))

        if scope == "-file":
            if rules:
                result.file_rules.update(rules)
            else:
                result.file_all = True
            continue

        target = index + 1 if scope == "-next-line" else index
        if target not in result.lines:
            result.lines[target] = rules or None
        else:
            existing = result.lines[target]
            if existing is None or not rules:
                result.lines[target] = None
            else:
                existing.update(rules)

    return result


def load_inline_ignores(filename: str) -> InlineIgnores:
    try:
        source = Path(filename).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return InlineIgnores()
    return parse_inline_ignores(source)


def apply_suppressions(
    filename: str,
    results: list[CheckResult],
    config: Config,
    inline: InlineIgnores | None = None,
) -> list[CheckResult]:
    """Remove suppressed violations and record why they were suppressed."""
    if inline is None:
        inline = load_inline_ignores(filename)

    for result in results:
        if result.skipped:
            continue

        kept = []
        for violation in result.violations:
            reason = _suppression_reason(
                filename, result.check_name, violation, config, inline
            )
            if reason is None:
                kept.append(violation)
            else:
                result.suppressed[reason] = result.suppressed.get(reason, 0) + 1

        result.violations = kept
        result.passed = not any(v.severity == Severity.ERROR for v in kept)

    return results


def _suppression_reason(
    filename: str,
    check_name: str,
    violation,
    config: Config,
    inline: InlineIgnores,
) -> str | None:
    # Secrets can only be allowlisted in codewatch.yaml, never inline.
    if check_name != "secrets" and inline.ignores(violation.line, violation.rule_id):
        return "inline"
    if config.allows(filename, check_name, violation.rule_id):
        return "config"
    return None
