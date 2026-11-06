"""Tests for the secrets check."""

from codewatch.checks.secrets import check_secrets
from codewatch.types import Severity


def test_clean_code_passes():
    lines = [
        'api_url = os.environ.get("API_URL")',
        'password = os.environ["DB_PASSWORD"]',
        "def connect(host, port):",
    ]
    result = check_secrets("app.py", lines)
    assert result.passed
    assert result.violations == []


def test_hardcoded_password_flagged():
    lines = ['password = "supersecret123"']
    result = check_secrets("app.py", lines)
    assert len(result.violations) == 1
    assert result.violations[0].severity == Severity.ERROR


def test_hardcoded_api_key_flagged():
    lines = ['api_key = "sk-abc123xyz789longkey"']
    result = check_secrets("app.py", lines)
    assert len(result.violations) == 1


def test_numeric_suffix_flagged():
    lines = ['']
    result = check_secrets("app.py", lines)
    assert len(result.violations) == 1
    assert result.violations[0].severity == Severity.ERROR


def test_aws_key_flagged():
    lines = ["aws_access = 'AKIAIOSFODNN7EXAMPLE'"]
    result = check_secrets("app.py", lines)
    assert len(result.violations) == 1


def test_comment_with_example_ignored():
    lines = ['# example: api_key = "your-api-key-here"']
    result = check_secrets("app.py", lines)
    assert result.violations == []


def test_placeholder_ignored():
    lines = ['token = "<your-token-here>"']
    result = check_secrets("app.py", lines)
    assert result.violations == []


def test_secret_uses_file_line_number(tmp_path, monkeypatch):
    src = tmp_path / "app.py"
    src.write_text('x = 1\n\npassword = "supersecret123"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = check_secrets("app.py", ['password = "supersecret123"'])
    assert result.violations[0].line == 3
