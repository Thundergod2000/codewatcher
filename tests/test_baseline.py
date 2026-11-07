"""Tests for the accepted-findings baseline."""

import json

import pytest

from codewatch.baseline import (
    Baseline,
    BaselineEntry,
    BaselineError,
    entries_from_results,
    load_baseline,
    write_baseline,
)
from codewatch.types import (
    CheckResult,
    Severity,
    Violation,
    make_fingerprint,
)


def _violation(rule_id="CW-DOC-001", filename="app.py", detail="public", **kwargs):
    severity = kwargs.pop("severity", Severity.WARNING)
    return Violation(
        line=1,
        message="finding",
        severity=severity,
        rule_id=rule_id,
        fingerprint=make_fingerprint(rule_id, filename, detail),
        detail=detail,
        **kwargs,
    )


def test_write_and_load_roundtrip(tmp_path):
    path = tmp_path / ".codewatch-baseline.json"
    entries = [
        BaselineEntry("CW-DOC-001", "b.py", "sha256:2"),
        BaselineEntry("CW-COMPLEX-001", "a.py", "sha256:1", "run", 34),
    ]

    write_baseline(path, entries)
    baseline = load_baseline(path)

    assert baseline.path == path
    assert [entry.file for entry in baseline.entries] == ["a.py", "b.py"]
    assert baseline.entries[0].function == "run"
    assert baseline.entries[0].complexity == 34


def test_write_is_deterministic_and_sorted(tmp_path):
    path = tmp_path / ".codewatch-baseline.json"
    entries = [
        BaselineEntry("CW-DOC-001", "z.py", "sha256:b"),
        BaselineEntry("CW-DOC-001", "a.py", "sha256:a"),
    ]

    write_baseline(path, entries)
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["schema_version"] == 1
    assert data["generated_at"].endswith("Z")
    assert [entry["file"] for entry in data["entries"]] == ["a.py", "z.py"]


def test_write_rejects_secret_entries(tmp_path):
    path = tmp_path / ".codewatch-baseline.json"
    entries = [BaselineEntry("CW-SECRET-004", "app.py", "sha256:secret")]
    with pytest.raises(BaselineError):
        write_baseline(path, entries)


def test_apply_suppresses_matching_violation():
    violation = _violation()
    result = CheckResult(
        check_name="docstrings",
        passed=True,
        violations=[violation],
    )
    baseline = Baseline(entries=[
        BaselineEntry("CW-DOC-001", "app.py", violation.fingerprint),
    ])

    baseline.apply("app.py", [result])

    assert result.violations == []
    assert result.suppressed == {"baseline": 1}
    assert violation.fingerprint in baseline.matched


def test_apply_ignores_other_files():
    violation = _violation(filename="other.py")
    result = CheckResult(check_name="docstrings", passed=True, violations=[violation])
    baseline = Baseline(entries=[
        BaselineEntry("CW-DOC-001", "app.py", violation.fingerprint),
    ])

    baseline.apply("other.py", [result])

    assert result.violations == [violation]
    assert result.suppressed == {}


def test_apply_never_suppresses_secrets():
    violation = _violation(rule_id="CW-SECRET-004")
    result = CheckResult(check_name="secrets", passed=False, violations=[violation])
    baseline = Baseline(entries=[
        BaselineEntry("CW-SECRET-004", "app.py", violation.fingerprint),
    ])

    baseline.apply("app.py", [result])

    assert result.violations == [violation]
    assert result.suppressed == {}


def test_stale_entries_only_for_scanned_files():
    matched = _violation(filename="app.py")
    stale = _violation(filename="app.py", detail="other")
    untouched = _violation(filename="legacy/old.py")

    baseline = Baseline(entries=[
        BaselineEntry("CW-DOC-001", "app.py", matched.fingerprint),
        BaselineEntry("CW-DOC-001", "app.py", stale.fingerprint),
        BaselineEntry("CW-DOC-001", "legacy/old.py", untouched.fingerprint),
    ])

    result = CheckResult(check_name="docstrings", passed=True, violations=[matched])
    baseline.apply("app.py", [result])

    assert baseline.stale({"app.py"}) == [baseline.entries[1]]


def test_entries_from_results_skips_secrets_and_records_metric():
    secret = _violation(rule_id="CW-SECRET-004")
    complexity = _violation(
        rule_id="CW-COMPLEX-001",
        detail="run",
        metric=34,
        severity=Severity.ERROR,
    )
    results = {
        "app.py": [
            CheckResult(check_name="secrets", passed=False, violations=[secret]),
            CheckResult(check_name="complexity", passed=False, violations=[complexity]),
        ]
    }

    entries = entries_from_results(results)

    assert [entry.rule_id for entry in entries] == ["CW-COMPLEX-001"]
    assert entries[0].function == "run"
    assert entries[0].complexity == 34


@pytest.mark.parametrize(
    "text",
    [
        "{not json",
        "[]",
        '{"schema_version": 2, "entries": []}',
        '{"schema_version": 1, "entries": [], "unknown": 1}',
        '{"schema_version": 1, "generated_at": 5, "entries": []}',
        '{"schema_version": 1, "entries": [{"rule_id": "CW-SECRET-004", '
        '"file": "a.py", "fingerprint": "x"}]}',
        '{"schema_version": 1, "entries": [{"rule_id": "CW-NOPE-999", '
        '"file": "a.py", "fingerprint": "x"}]}',
        '{"schema_version": 1, "entries": [{"rule_id": "CW-DOC-001", '
        '"file": "a.py"}]}',
        '{"schema_version": 1, "entries": [{"rule_id": "CW-DOC-001", '
        '"file": "a.py", "fingerprint": "x", "bogus": 1}]}',
        '{"schema_version": 1, "entries": [{"rule_id": "CW-DOC-001", '
        '"file": "a.py", "fingerprint": "x", "complexity": "high"}]}',
    ],
)
def test_invalid_baseline_fails_closed(tmp_path, text):
    path = tmp_path / ".codewatch-baseline.json"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(BaselineError):
        load_baseline(path)


def test_missing_baseline_is_empty(tmp_path):
    baseline = load_baseline(tmp_path / ".codewatch-baseline.json")

    assert baseline.entries == []
    assert baseline.path is None
