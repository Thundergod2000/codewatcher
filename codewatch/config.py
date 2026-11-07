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

TOP_LEVEL_KEYS = {"version", "allow", "disable", "thresholds", "docstrings"}
_ALLOW_KEYS = {"path", "checks", "rules", "reason"}
_THRESHOLD_KEYS = {"complexity"}
_COMPLEXITY_THRESHOLD_KEYS = {"warn", "error"}
_DEFAULT_COMPLEXITY_WARN = 10
_DEFAULT_COMPLEXITY_ERROR = 20
_DOCSTRING_KEYS = {"require_exports", "require_components"}
_DEFAULT_REQUIRE_EXPORTS = True
_DEFAULT_REQUIRE_COMPONENTS = True
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
    disable: frozenset[str] = field(default_factory=frozenset)
    thresholds: dict = field(default_factory=dict)
    docstrings: dict = field(default_factory=dict)

    def allows(self, filename: str, check_name: str, rule_id: str) -> bool:
        return any(
            rule.matches(filename, check_name, rule_id) for rule in self.allow
        )

    def is_disabled(self, check_name: str) -> bool:
        return check_name in self.disable

    def complexity_thresholds(self) -> tuple[int, int]:
        complexity = self.thresholds.get("complexity", {}) if isinstance(
            self.thresholds, dict
        ) else {}
        warn = complexity.get("warn", _DEFAULT_COMPLEXITY_WARN)
        error = complexity.get("error", _DEFAULT_COMPLEXITY_ERROR)
        if not isinstance(warn, int) or isinstance(warn, bool):
            warn = _DEFAULT_COMPLEXITY_WARN
        if not isinstance(error, int) or isinstance(error, bool):
            error = _DEFAULT_COMPLEXITY_ERROR
        return warn, error

    def require_docstring_exports(self) -> bool:
        return self._docstring_flag("require_exports", _DEFAULT_REQUIRE_EXPORTS)

    def require_docstring_components(self) -> bool:
        return self._docstring_flag("require_components", _DEFAULT_REQUIRE_COMPONENTS)

    def _docstring_flag(self, key: str, default: bool) -> bool:
        docstrings = self.docstrings if isinstance(self.docstrings, dict) else {}
        value = docstrings.get(key, default)
        if not isinstance(value, bool):
            return default
        return value


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

    unknown = set(data) - TOP_LEVEL_KEYS
    if unknown:
        raise ConfigError(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")

    version = data.get("version", 1)
    if version != 1:
        raise ConfigError(
            f"{path}: unsupported version {version!r} (expected 1)"
        )

    raw_allow = data.get("allow") or []
    if not isinstance(raw_allow, list):
        raise ConfigError(f"{path}: 'allow' must be a list")

    allow = [
        _parse_allow(entry, index, path)
        for index, entry in enumerate(raw_allow)
    ]

    raw_disable = data.get("disable") or []
    if not isinstance(raw_disable, list) or any(
        not isinstance(item, str) for item in raw_disable
    ):
        raise ConfigError(f"{path}: 'disable' must be a list of check names")
    unknown_checks = set(raw_disable) - KNOWN_CHECKS
    if unknown_checks:
        raise ConfigError(
            f"{path}: unknown check(s) in 'disable': "
            f"{', '.join(sorted(unknown_checks))}"
        )
    disable = frozenset(raw_disable)

    raw_thresholds = data.get("thresholds") or {}
    if not isinstance(raw_thresholds, dict):
        raise ConfigError(f"{path}: 'thresholds' must be a mapping")
    unknown_threshold_keys = set(raw_thresholds) - _THRESHOLD_KEYS
    if unknown_threshold_keys:
        raise ConfigError(
            f"{path}: unknown threshold key(s): "
            f"{', '.join(sorted(unknown_threshold_keys))}"
        )
    thresholds = _parse_thresholds(raw_thresholds, path)

    raw_docstrings = data.get("docstrings") or {}
    if not isinstance(raw_docstrings, dict):
        raise ConfigError(f"{path}: 'docstrings' must be a mapping")
    unknown_docstring_keys = set(raw_docstrings) - _DOCSTRING_KEYS
    if unknown_docstring_keys:
        raise ConfigError(
            f"{path}: 'docstrings' unknown key(s): "
            f"{', '.join(sorted(unknown_docstring_keys))}"
        )
    docstrings = _parse_docstrings(raw_docstrings, path)

    return Config(
        allow=allow, disable=disable, thresholds=thresholds, docstrings=docstrings
    )


def _parse_docstrings(raw: dict, path: Path) -> dict:
    where = f"{path}: docstrings"
    docstrings = {}
    for key in _DOCSTRING_KEYS:
        value = raw.get(key)
        if value is None:
            continue
        if not isinstance(value, bool):
            raise ConfigError(f"{where}.{key} must be a boolean")
        docstrings[key] = value
    return docstrings


def _parse_thresholds(raw: dict, path: Path) -> dict:
    where = f"{path}: thresholds"
    raw_complexity = raw.get("complexity") or {}
    if not isinstance(raw_complexity, dict):
        raise ConfigError(f"{where}.complexity must be a mapping")
    unknown_keys = set(raw_complexity) - _COMPLEXITY_THRESHOLD_KEYS
    if unknown_keys:
        raise ConfigError(
            f"{where}.complexity: unknown key(s): "
            f"{', '.join(sorted(unknown_keys))}"
        )

    complexity = {}
    warn = raw_complexity.get("warn")
    if warn is None:
        warn = _DEFAULT_COMPLEXITY_WARN
    error = raw_complexity.get("error")
    if error is None:
        error = _DEFAULT_COMPLEXITY_ERROR
    if not isinstance(warn, int) or isinstance(warn, bool):
        raise ConfigError(f"{where}.complexity.warn must be an integer")
    if not isinstance(error, int) or isinstance(error, bool):
        raise ConfigError(f"{where}.complexity.error must be an integer")
    complexity["warn"] = warn
    complexity["error"] = error
    return {"complexity": complexity}


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
