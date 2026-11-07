"""Accepted-findings baseline: suppress pre-existing debt, never secrets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from codewatch.config import KNOWN_RULE_IDS
from codewatch.diff import (
    clear_line_number_cache,
    is_ignored_path,
    list_tracked_files,
    use_all_lines,
)
from codewatch.types import SCHEMA_VERSION, CheckResult, Severity

BASELINE_FILENAME = ".codewatch-baseline.json"
SECRET_RULE_PREFIX = "CW-SECRET-"

_TOP_LEVEL_KEYS = {"schema_version", "generated_at", "entries"}
_ENTRY_KEYS = {"rule_id", "file", "fingerprint", "function", "complexity"}
_REQUIRED_ENTRY_KEYS = ("rule_id", "file", "fingerprint")


class BaselineError(Exception):
    """Raised when a baseline file is malformed or tries to hide a secret."""


@dataclass(frozen=True)
class BaselineEntry:
    rule_id: str
    file: str
    fingerprint: str
    function: str = ""
    complexity: int | None = None

    def to_dict(self) -> dict:
        data = {
            "rule_id": self.rule_id,
            "file": self.file,
            "fingerprint": self.fingerprint,
        }
        if self.function:
            data["function"] = self.function
        if self.complexity is not None:
            data["complexity"] = self.complexity
        return data

    def sort_key(self) -> tuple:
        return (self.file, self.rule_id, self.function, self.fingerprint)


@dataclass
class Baseline:
    entries: list[BaselineEntry] = field(default_factory=list)
    generated_at: str = ""
    path: Path | None = None
    matched: set[str] = field(default_factory=set)

    def apply(
        self, filename: str, results: list[CheckResult]
    ) -> list[CheckResult]:
        """Remove violations whose fingerprint is in the baseline."""
        target = _normalize(filename)
        fingerprints = {
            entry.fingerprint
            for entry in self.entries
            if entry.file == target
        }
        if not fingerprints:
            return results

        for result in results:
            if result.skipped:
                continue

            kept = []
            for violation in result.violations:
                if (
                    violation.fingerprint in fingerprints
                    and not violation.rule_id.startswith(SECRET_RULE_PREFIX)
                ):
                    self.matched.add(violation.fingerprint)
                    result.suppressed["baseline"] = (
                        result.suppressed.get("baseline", 0) + 1
                    )
                else:
                    kept.append(violation)

            result.violations = kept
            result.passed = not any(
                v.severity == Severity.ERROR for v in kept
            )

        return results

    def stale(self, scanned_files: set[str]) -> list[BaselineEntry]:
        """Return entries for scanned files that no longer match a finding."""
        scanned = {_normalize(name) for name in scanned_files}
        return [
            entry
            for entry in self.entries
            if entry.file in scanned and entry.fingerprint not in self.matched
        ]


def find_baseline(start: Path | None = None) -> Path | None:
    """Return the nearest baseline file, stopping at the repository root."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / BASELINE_FILENAME
        if candidate.is_file():
            return candidate
        if (directory / ".git").exists():
            break
    return None


def load_baseline(path: Path | None = None) -> Baseline:
    """Load and validate the baseline. A missing file means an empty baseline."""
    if path is None:
        path = find_baseline()
    if path is None or not Path(path).is_file():
        return Baseline()

    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BaselineError(f"could not read {path}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BaselineError(f"invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise BaselineError(f"{path}: top level must be an object")

    unknown = set(data) - _TOP_LEVEL_KEYS
    if unknown:
        raise BaselineError(
            f"{path}: unknown key(s): {', '.join(sorted(unknown))}"
        )

    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise BaselineError(
            f"{path}: unsupported schema_version {version!r}"
            f" (expected {SCHEMA_VERSION})"
        )

    raw_entries = data.get("entries", [])
    if not isinstance(raw_entries, list):
        raise BaselineError(f"{path}: 'entries' must be a list")

    entries = [
        _parse_entry(item, index, path)
        for index, item in enumerate(raw_entries, start=1)
    ]

    generated_at = data.get("generated_at", "")
    if not isinstance(generated_at, str):
        raise BaselineError(f"{path}: 'generated_at' must be a string")

    return Baseline(entries=entries, generated_at=generated_at, path=path)


def _parse_entry(item, index: int, path: Path) -> BaselineEntry:
    where = f"{path}: entries[{index}]"

    if not isinstance(item, dict):
        raise BaselineError(f"{where} must be an object")

    unknown = set(item) - _ENTRY_KEYS
    if unknown:
        raise BaselineError(
            f"{where}: unknown key(s): {', '.join(sorted(unknown))}"
        )

    for key in _REQUIRED_ENTRY_KEYS:
        value = item.get(key)
        if not isinstance(value, str) or not value:
            raise BaselineError(f"{where}: '{key}' must be a non-empty string")

    rule_id = item["rule_id"]
    if rule_id.startswith(SECRET_RULE_PREFIX):
        raise BaselineError(
            f"{where}: {rule_id} cannot be baselined — secrets are never suppressed"
        )
    if rule_id not in KNOWN_RULE_IDS:
        raise BaselineError(f"{where}: unknown rule {rule_id!r}")

    function = item.get("function", "")
    if function is None:
        function = ""
    if not isinstance(function, str):
        raise BaselineError(f"{where}: 'function' must be a string")

    complexity = item.get("complexity")
    if complexity is not None and (
        isinstance(complexity, bool) or not isinstance(complexity, int)
    ):
        raise BaselineError(f"{where}: 'complexity' must be an integer")

    return BaselineEntry(
        rule_id=rule_id,
        file=_normalize(item["file"]),
        fingerprint=item["fingerprint"],
        function=function,
        complexity=complexity,
    )


def entries_from_results(
    results: dict[str, list[CheckResult]],
) -> list[BaselineEntry]:
    """Build sorted baseline entries from a scan. Secrets are never included."""
    entries: dict[tuple, BaselineEntry] = {}

    for filename, file_results in results.items():
        for result in file_results:
            if result.skipped:
                continue
            for violation in result.violations:
                if violation.rule_id.startswith(SECRET_RULE_PREFIX):
                    continue
                if not violation.fingerprint:
                    continue
                entry = BaselineEntry(
                    rule_id=violation.rule_id,
                    file=_normalize(filename),
                    fingerprint=violation.fingerprint,
                    function=violation.detail,
                    complexity=violation.metric,
                )
                entries[entry.sort_key()] = entry

    return [entries[key] for key in sorted(entries)]


def write_baseline(path: Path, entries: list[BaselineEntry]) -> None:
    """Write a deterministic baseline file. Callers must review the result."""
    ordered = sorted(entries, key=lambda entry: entry.sort_key())
    for entry in ordered:
        if entry.rule_id.startswith(SECRET_RULE_PREFIX):
            raise BaselineError(
                f"{entry.rule_id} cannot be baselined — secrets are never suppressed"
            )
        if entry.rule_id not in KNOWN_RULE_IDS:
            raise BaselineError(f"unknown rule {entry.rule_id!r}")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entries": [entry.to_dict() for entry in ordered],
    }
    text = json.dumps(payload, indent=2) + "\n"

    path = Path(path)
    try:
        path.write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise BaselineError(f"could not write {path}: {exc}") from exc


def collect_project_files() -> dict[str, list[str]]:
    """Read every tracked supported file and treat all of its lines as added."""
    clear_line_number_cache()
    files: dict[str, list[str]] = {}

    for filename in list_tracked_files():
        if is_ignored_path(filename):
            continue
        try:
            source = Path(filename).read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue
        lines = source.splitlines()
        use_all_lines(filename, len(lines))
        files[filename] = lines

    return files


def _normalize(value: str) -> str:
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return re.sub(r"/+", "/", normalized)
