"""Tests for codewatch.yaml allowlist config."""

import pytest

from codewatch.config import (
    Config,
    ConfigError,
    find_config,
    load_config,
)


def _write(tmp_path, text: str):
    path = tmp_path / "codewatch.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_config_is_empty(tmp_path):
    config = load_config(tmp_path / "codewatch.yaml")
    assert config.allow == []
    assert not config.allows("app.py", "secrets", "CW-SECRET-004")


def test_valid_config_loads_allow_rules(tmp_path):
    path = _write(
        tmp_path,
        "version: 1\n"
        "allow:\n"
        "  - path: 'tests/fixtures/**'\n"
        "    checks: [secrets]\n"
        "    reason: 'fake credentials'\n",
    )
    config = load_config(path)

    assert config.allows("tests/fixtures/key.py", "secrets", "CW-SECRET-004")
    assert not config.allows("app.py", "secrets", "CW-SECRET-004")
    assert not config.allows("tests/fixtures/key.py", "complexity", "CW-COMPLEX-001")
    assert config.allow[0].reason == "fake credentials"


def test_exact_file_and_directory_paths(tmp_path):
    path = _write(
        tmp_path,
        "version: 1\n"
        "allow:\n"
        "  - path: 'app.py'\n"
        "    checks: [secrets]\n"
        "  - path: 'legacy'\n"
        "    checks: [complexity]\n",
    )
    config = load_config(path)

    assert config.allows("app.py", "secrets", "CW-SECRET-004")
    assert not config.allows("app.pyc", "secrets", "CW-SECRET-004")
    assert config.allows("legacy/old.py", "complexity", "CW-COMPLEX-001")
    assert not config.allows("legacyish/old.py", "complexity", "CW-COMPLEX-001")


def test_rule_specific_allow(tmp_path):
    path = _write(
        tmp_path,
        "version: 1\n"
        "allow:\n"
        "  - path: 'app.py'\n"
        "    rules: [CW-SECRET-004]\n",
    )
    config = load_config(path)

    assert config.allows("app.py", "secrets", "CW-SECRET-004")
    assert not config.allows("app.py", "secrets", "CW-SECRET-005")


def test_path_separators_are_normalized(tmp_path):
    path = _write(
        tmp_path,
        "version: 1\n"
        "allow:\n"
        "  - path: 'pkg\\\\mod.py'\n"
        "    checks: [secrets]\n",
    )
    config = load_config(path)

    assert config.allows("pkg/mod.py", "secrets", "CW-SECRET-004")


def test_find_config_stops_at_repo_root(tmp_path):
    (tmp_path / ".git").mkdir()
    config_path = _write(tmp_path, "version: 1\n")
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)

    assert find_config(nested) == config_path.resolve()


@pytest.mark.parametrize(
    "text",
    [
        "version: 1\nunknown: true\n",
        "version: 2\n",
        "version: 1\nallow: not-a-list\n",
        "version: 1\nallow:\n  - path: 'a.py'\n    bogus: 1\n",
        "version: 1\nallow:\n  - checks: [secrets]\n",
        "version: 1\nallow:\n  - path: '/etc/passwd'\n    checks: [secrets]\n",
        "version: 1\nallow:\n  - path: '../outside.py'\n    checks: [secrets]\n",
        "version: 1\nallow:\n  - path: 'a.py'\n    checks: [not_a_check]\n",
        "version: 1\nallow:\n  - path: 'a.py'\n    rules: [CW-NOPE-999]\n",
        "version: [unclosed\n",
    ],
)
def test_invalid_config_fails_closed(tmp_path, text):
    path = _write(tmp_path, text)
    with pytest.raises(ConfigError):
        load_config(path)


def test_empty_file_is_empty_config(tmp_path):
    path = _write(tmp_path, "")
    assert load_config(path) == Config()


def test_disable_parses_check_names(tmp_path):
    path = _write(
        tmp_path,
        "version: 1\n"
        "disable:\n"
        "  - docstrings\n"
        "  - test_presence\n",
    )
    config = load_config(path)
    assert config.is_disabled("docstrings")
    assert config.is_disabled("test_presence")
    assert not config.is_disabled("secrets")


def test_disable_rejects_unknown_check(tmp_path):
    path = _write(tmp_path, "version: 1\ndisable:\n  - not_a_check\n")
    with pytest.raises(ConfigError):
        load_config(path)


def test_thresholds_parse_complexity(tmp_path):
    path = _write(
        tmp_path,
        "version: 1\n"
        "thresholds:\n"
        "  complexity:\n"
        "    warn: 15\n"
        "    error: 30\n",
    )
    config = load_config(path)
    warn, error = config.complexity_thresholds()
    assert (warn, error) == (15, 30)


def test_thresholds_default_to_module_defaults(tmp_path):
    path = _write(tmp_path, "version: 1\n")
    config = load_config(path)
    assert config.complexity_thresholds() == (10, 20)


def test_thresholds_uses_defaults_for_missing_keys(tmp_path):
    path = _write(
        tmp_path,
        "version: 1\n"
        "thresholds:\n"
        "  complexity:\n"
        "    warn: 7\n",
    )
    config = load_config(path)
    assert config.complexity_thresholds() == (7, 20)


@pytest.mark.parametrize(
    "text",
    [
        "version: 1\nthresholds:\n  not_a_check:\n    warn: 5\n",
        "version: 1\nthresholds:\n  complexity:\n    bogus: 5\n",
        "version: 1\nthresholds:\n  complexity:\n    warn: not-a-number\n",
        "version: 1\nthresholds:\n  complexity:\n    error: true\n",
        "version: 1\nthresholds: not-a-mapping\n",
    ],
)
def test_invalid_thresholds_fail_closed(tmp_path, text):
    path = _write(tmp_path, text)
    with pytest.raises(ConfigError):
        load_config(path)
