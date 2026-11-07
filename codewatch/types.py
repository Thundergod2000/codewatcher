"""Shared data types for all checks."""

import hashlib
from dataclasses import dataclass, field
from enum import Enum

SCHEMA_VERSION = 1


class Severity(str, Enum):
    ERROR = "error"    # blocks push
    WARNING = "warn"   # warns but allows


@dataclass
class Violation:
    line: int
    message: str
    severity: Severity = Severity.WARNING
    rule_id: str = ""
    fingerprint: str = ""
    detail: str = ""            # stable identifier such as a function name
    metric: int | None = None   # measured value such as cyclomatic complexity


@dataclass
class CheckResult:
    check_name: str
    passed: bool
    violations: list[Violation] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""
    suppressed: dict[str, int] = field(default_factory=dict)


def make_fingerprint(rule_id: str, filename: str, detail: str = "") -> str:
    """Return a stable SHA-256 identity for a violation.

    The detail is normalized whitespace so a moved or re-indented line keeps
    the same fingerprint. The raw detail is never returned, only its hash.
    """
    normalized_detail = " ".join(detail.split())
    normalized_path = filename.replace("\\", "/")
    payload = "\0".join((rule_id, normalized_path, normalized_detail))
    digest = hashlib.sha256(payload.encode("utf-8", "surrogateescape")).hexdigest()
    return f"sha256:{digest}"
