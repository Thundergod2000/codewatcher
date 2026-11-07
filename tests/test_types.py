"""Tests for shared violation identity."""

from codewatch.types import SCHEMA_VERSION, Severity, Violation, make_fingerprint


def test_schema_version_is_pinned():
    assert SCHEMA_VERSION == 1


def test_violation_defaults_are_empty_identity():
    violation = Violation(line=1, message="x")
    assert violation.rule_id == ""
    assert violation.fingerprint == ""
    assert violation.severity == Severity.WARNING


def test_fingerprint_is_stable_across_whitespace():
    first = make_fingerprint("CW-DEAD-001", "a.py", "  unused var  ")
    second = make_fingerprint("CW-DEAD-001", "a.py", "unused var")
    assert first == second


def test_fingerprint_normalizes_path_separators():
    windows = make_fingerprint("CW-DEAD-001", "pkg\\mod.py", "name")
    posix = make_fingerprint("CW-DEAD-001", "pkg/mod.py", "name")
    assert windows == posix


def test_fingerprint_changes_with_rule_and_detail():
    base = make_fingerprint("CW-DEAD-001", "a.py", "name")
    assert base != make_fingerprint("CW-DOC-001", "a.py", "name")
    assert base != make_fingerprint("CW-DEAD-001", "a.py", "other")


def test_fingerprint_never_contains_raw_detail():
    fingerprint = make_fingerprint("CW-SECRET-004", "a.py", "password = 'hunter2'")
    assert fingerprint.startswith("sha256:")
    assert "hunter2" not in fingerprint
