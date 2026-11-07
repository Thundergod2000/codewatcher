"""Load and validate codewatch.yaml allowlists."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_FILENAME = "codewatch.yaml"

KNOWN_CHECKS = frozenset({
    "secrets",
    "complexity",
    "dead_code",
    "test_presence",
    "docstrings",
})

KNOWN_RULE_IDS = frozenset({
    "CW-SECRET-001", "CW-SECRET-002", "CW-SECRET-003", "CW-SECRET-004",
    "CW-SECRET-005", "CW-SECRET-006", "CW-SECRET-007", "CW-SECRET-008",
    "CW-SECRET-009",
    "CW-COMPLEX-001", "CW-COMPLEX-002",
    "CW-DEAD-001",
    "CW-TEST-001",
    "CW-DOC-001",
})

_TOP_LEVEL_KEYS = {"version", "allow"}
_ALLOW_KEYS = {"path", "checks", "rules", "reason"}
_GLOB_CACHE: dict[str, re.Pattern] = {}


class ConfigError(Exception):
    """Raised when codewatch.yaml is missing, malformed, or invalid."""


@dataclass(frozen=True)
class AllowRule:
    path: str
    checks: frozenset[str] = frozenset()
    rules: frozenset[str] = frozenset()
    reason: str = ""

    def matches(self, filename: str, check_name: str, rule_id: str) -> bool:
        if not _path_matches(filename, self.path):
            return False
        if self.checks and check_name not in self.checks:
            return False
        if self.rules and rule_id not in self.rules:
            return False
        return True


@dataclass
class Config:
    allow: list[AllowRule] = field(default_factory=list)

    def allows(self, filename: str, check_name: str, rule_id: str) -> bool:
        return any(
            rule.matches(filename, check_name, rule_id) for rule in self.allow
        )


def find_config(start: Path | None = None) -> Path | None:
    """Return the nearest codewatch.yaml, stopping at the repository root."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        if (directory / ".git").exists():
            break
    return None


def load_config(path: Path | None = None) -> Config:
    """Load and validate a config file. Missing file means an empty config."""
    if path is None:
        path = find_config()
    if path is None or not Path(path).is_file():
        return Config()

    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"could not read {path}: {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc

    return _parse(data, path)


def _parse(data, path: Path) -> Config:
    if data is None:
        return Config()

    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")

    unknown = set(data) - _TOP_LEVEL_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")

    version = data.get("version", 1)
    if version != 1:
        raise ConfigError(
            f"{path}: unsupported version {version!r} (expected 1)"
        )

    raw_allow = data.get("allow", [])
    if not isinstance(raw_allow, list):
        raise ConfigError(f"{path}: 'allow' must be a list")

    allow = [
        _parse_allow(entry, index, path)
        for index, entry in enumerate(raw_allow)
    ]
    return Config(allow=allow)


def _parse_allow(entry, index: int, path: Path) -> AllowRule:
    where = f"{path}: allow[{index}]"

    if not isinstance(entry, dict):
        raise ConfigError(f"{where} must be a mapping")

    unknown = set(entry) - _ALLOW_KEYS
    if unknown:
        raise ConfigError(f"{where}: unknown key(s): {', '.join(sorted(unknown))}")

    raw_path = entry.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ConfigError(f"{where}: 'path' must be a non-empty string")

    normalized = _normalize_path(raw_path)
    if _is_absolute(raw_path) or ".." in normalized.split("/"):
        raise ConfigError(f"{where}: path must stay inside the repository")

    checks = _string_list(entry.get("checks"), f"{where}.checks")
    unknown_checks = checks - KNOWN_CHECKS
    if unknown_checks:
        raise ConfigError(
            f"{where}: unknown check(s): {', '.join(sorted(unknown_checks))}"
        )

    rules = _string_list(entry.get("rules"), f"{where}.rules")
    unknown_rules = rules - KNOWN_RULE_IDS
    if unknown_rules:
        raise ConfigError(
            f"{where}: unknown rule(s): {', '.join(sorted(unknown_rules))}"
        )

    reason = entry.get("reason", "")
    if reason is None:
        reason = ""
    if not isinstance(reason, str):
        raise ConfigError(f"{where}: 'reason' must be a string")

    return AllowRule(
        path=normalized,
        checks=frozenset(checks),
        rules=frozenset(rules),
        reason=reason,
    )


def _string_list(value, where: str) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise ConfigError(f"{where} must be a list of strings")
    return set(value)


def _is_absolute(value: str) -> bool:
    return (
        value.startswith("/")
        or value.startswith("\\")
        or re.match(r"^[A-Za-z]:", value) is not None
    )


def _normalize_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    normalized = re.sub(r"/+", "/", normalized)
    return normalized.lstrip("/")


def _has_glob(pattern: str) -> bool:
    return any(ch in pattern for ch in "*?[")


def _path_matches(filename: str, pattern: str) -> bool:
    candidate = _normalize_path(filename)
    pattern = _normalize_path(pattern)
    if _has_glob(pattern):
        return _glob_regex(pattern).match(candidate) is not None
    return candidate == pattern or candidate.startswith(pattern.rstrip("/") + "/")


def _glob_regex(pattern: str) -> re.Pattern:
    cached = _GLOB_CACHE.get(pattern)
    if cached is not None:
        return cached

    parts: list[str] = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if pattern[index:index + 2] == "**":
                if pattern[index:index + 3] == "**/":
                    parts.append("(?:.*/)?")
                    index += 3
                else:
                    parts.append(".*")
                    index += 2
            else:
                parts.append("[^/]*")
                index += 1
        elif char == "?":
            parts.append("[^/]")
            index += 1
        elif char == "[":
            end = pattern.find("]", index + 1)
            if end == -1:
                parts.append(re.escape(char))
                index += 1
            else:
                parts.append(pattern[index:end + 1])
                index = end + 1
        else:
            parts.append(re.escape(char))
            index += 1

    compiled = re.compile("^" + "".join(parts) + "$")
    _GLOB_CACHE[pattern] = compiled
    return compiled
