"""Detect hardcoded secrets in JavaScript/TypeScript changed lines."""

from __future__ import annotations
import re
from codewatch.diff import added_file_linenos
from codewatch.types import CheckResult, Violation, Severity, make_fingerprint

# Patterns that indicate a hardcoded secret in JS/TS
_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("CW-SECRET-001", "AWS access key", re.compile(r"AKIA[0-9A-Z]{16}", re.I)),
    ("CW-SECRET-002", "AWS secret key", re.compile(r"aws[_.]?(?:secret|key)\s*[:=]\s*['\"][^'\"]{20,}", re.I)),
    ("CW-SECRET-003", "Private key block", re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE KEY-----")),
    ("CW-SECRET-004", "Password assignment", re.compile(r"(?:password|passwd|pwd)(?:_?\d+)?\s*[:=]\s*['\"][^'\"]{4,}['\"]", re.I)),
    ("CW-SECRET-005", "API key assignment", re.compile(r"(?:api[_.]?key|apikey)(?:_?\d+)?\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.I)),
    ("CW-SECRET-006", "Secret assignment", re.compile(r"(?:secret|token)(?:_?\d+)?\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.I)),
    ("CW-SECRET-007", "Generic bearer token", re.compile(r"bearer\s+[a-zA-Z0-9\-_]{20,}", re.I)),
    ("CW-SECRET-008", "Hardcoded IP (non-local)", re.compile(
        r"\b(?!(?:127\.0\.0\.1|0\.0\.0\.0|localhost))"
        r"(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
    )),
    # JS/TS specific patterns
    ("CW-SECRET-009", "JWT secret", re.compile(r"(?:jwt|jwt_secret)\s*[:=]\s*['\"][^'\"]{16,}['\"]", re.I)),
]

# Lines that look like secrets but are almost certainly safe
_ALLOWLIST = re.compile(
    r"(?:^\s*//|^\s*/\*|placeholder|dummy|fake|your.?key|<.*?>|\$\{|\$\(|process\.env|getenv|import\.meta\.env)",
    re.I,
)


def check_js_secrets(filename: str, added_lines: list[str]) -> CheckResult:
    """
    Scan added lines for patterns that indicate hardcoded credentials in JS/TS.

    Blocks on any match — secrets in source control are always an error.
    """
    violations: list[Violation] = []
    linenos = added_file_linenos(filename, added_lines)

    for i, line in enumerate(added_lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue
        if _ALLOWLIST.search(stripped):
            continue

        for rule_id, label, pattern in _PATTERNS:
            if pattern.search(stripped):
                violations.append(Violation(
                    line=linenos[i],
                    message=f"{label} detected — move to environment variable or secrets manager",
                    severity=Severity.ERROR,
                    rule_id=rule_id,
                    fingerprint=make_fingerprint(rule_id, filename, stripped),
                ))
                break

    return CheckResult(
        check_name="secrets",
        passed=len(violations) == 0,
        violations=violations,
    )