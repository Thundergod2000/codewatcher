"""Tests for inline ignores and suppression filtering."""

from codewatch.scanner import run_checks
from codewatch.suppress import parse_inline_ignores


def test_ignore_on_same_line():
    ignores = parse_inline_ignores("x = 1  # codewatch: ignore\n")
    assert ignores.ignores(1, "CW-COMPLEX-001")
    assert not ignores.ignores(2, "CW-COMPLEX-001")


def test_ignore_next_line():
    ignores = parse_inline_ignores("# codewatch: ignore-next-line\nfoo()\n")
    assert ignores.ignores(2, "CW-DEAD-001")
    assert not ignores.ignores(1, "CW-DEAD-001")


def test_ignore_file():
    ignores = parse_inline_ignores("# codewatch: ignore-file\n")
    assert ignores.ignores(1, "CW-DOC-001")
    assert ignores.ignores(99, "CW-DEAD-001")


def test_ignore_specific_rule():
    ignores = parse_inline_ignores("foo()  # codewatch: ignore CW-DOC-001\n")
    assert ignores.ignores(1, "CW-DOC-001")
    assert not ignores.ignores(1, "CW-DEAD-001")


def test_ignore_works_in_js_comments():
    ignores = parse_inline_ignores("const x = 1; // codewatch: ignore\n")
    assert ignores.ignores(1, "CW-DEAD-001")


def test_inline_ignore_suppresses_warning(tmp_path, monkeypatch):
    source = "def public():  # codewatch: ignore CW-DOC-001\n    pass\n"
    (tmp_path / "app.py").write_text(source, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    added = ["def public():  # codewatch: ignore CW-DOC-001", "    pass"]
    results = run_checks({"app.py": added})
    docs = results["app.py"][4]

    assert docs.check_name == "docstrings"
    assert docs.violations == []
    assert docs.suppressed == {"inline": 1}


def test_secrets_cannot_be_inline_ignored(tmp_path, monkeypatch):
    line = 'password = "supersecret123"  # codewatch: ignore'
    (tmp_path / "app.py").write_text(line + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    results = run_checks({"app.py": [line]})
    secrets = results["app.py"][0]

    assert secrets.check_name == "secrets"
    assert secrets.violations
    assert "inline" not in secrets.suppressed


def test_config_can_allowlist_secrets(tmp_path, monkeypatch):
    (tmp_path / "codewatch.yaml").write_text(
        "version: 1\n"
        "allow:\n"
        "  - path: 'app.py'\n"
        "    checks: [secrets]\n"
        "    reason: 'test fixture'\n",
        encoding="utf-8",
    )
    line = 'password = "supersecret123"'
    (tmp_path / "app.py").write_text(line + "\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    results = run_checks({"app.py": [line]})
    secrets = results["app.py"][0]

    assert secrets.check_name == "secrets"
    assert secrets.violations == []
    assert secrets.passed is True
    assert secrets.suppressed == {"config": 1}
