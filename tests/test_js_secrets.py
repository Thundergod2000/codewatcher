"""Tests for the JS/TS secrets check."""

from codewatch.checks.js_secrets import check_js_secrets
from codewatch.types import Severity


def test_clean_js_code_passes():
    lines = [
        'const apiUrl = process.env.API_URL;',
        'const password = process.env.DB_PASSWORD;',
        "function connect(host, port) {",
        "    return host + ':' + port;",
        "}",
    ]
    result = check_js_secrets("app.js", lines)
    assert result.passed
    assert result.violations == []


def test_clean_ts_code_passes():
    lines = [
        'const apiUrl: string = process.env.API_URL;',
        'const password: string = process.env.DB_PASSWORD;',
        "function connect(host: string, port: number): string {",
        "    return host + ':' + port;",
        "}",
    ]
    result = check_js_secrets("app.ts", lines)
    assert result.passed
    assert result.violations == []


def test_hardcoded_password_flagged():
    lines = ['const password = "supersecret123";']
    result = check_js_secrets("app.js", lines)
    assert len(result.violations) == 1
    assert result.violations[0].severity == Severity.ERROR
    assert "Password assignment" in result.violations[0].message


def test_hardcoded_api_key_flagged():
    lines = ['const api_key = "sk-abc123xyz789longkey";']
    result = check_js_secrets("app.js", lines)
    assert len(result.violations) == 1


def test_api_key_with_numeric_suffix_flagged():
    lines = [''] 
    result = check_js_secrets("app.js", lines)
    assert len(result.violations) == 1
    assert result.violations[0].severity == Severity.ERROR


def test_numeric_suffix_with_underscore_flagged():
    lines = ['']
    result = check_js_secrets("app.js", lines)
    assert len(result.violations) == 1


def test_aws_key_flagged():
    lines = ["const aws_access = 'AKIAIOSFODNN7EXAMPLE';"]
    result = check_js_secrets("app.js", lines)
    assert len(result.violations) == 1


def test_comment_with_example_ignored():
    lines = ['// example: api_key = "your-api-key-here"']
    result = check_js_secrets("app.js", lines)
    assert result.violations == []


def test_placeholder_ignored():
    lines = ['const token = "<your-token-here>";']
    result = check_js_secrets("app.js", lines)
    assert result.violations == []


def test_env_var_usage_ignored():
    lines = [
        'const password = process.env.DB_PASSWORD;',
        'const apiKey = import.meta.env.VITE_API_KEY;',
    ]
    result = check_js_secrets("app.js", lines)
    assert result.violations == []


def test_jwt_secret_flagged():
    lines = ['const jwt_secret = "my-super-secret-jwt-key-that-is-long-enough";']
    result = check_js_secrets("app.js", lines)
    assert len(result.violations) == 1


def test_secret_uses_file_line_number(tmp_path, monkeypatch):
    src = tmp_path / "app.js"
    src.write_text('x = 1\n\nconst password = "supersecret123"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_js_secrets("app.js", ['const password = "supersecret123"'])
    assert result.violations[0].line == 3