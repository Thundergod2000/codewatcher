"""All checks — import from here."""

from codewatch.checks.complexity import check_complexity
from codewatch.checks.dead_code import check_dead_code
from codewatch.checks.secrets import check_secrets
from codewatch.checks.tests import check_test_presence
from codewatch.checks.docstrings import check_docstrings
from codewatch.checks.js_secrets import check_js_secrets
from codewatch.checks.js_complexity import check_js_complexity
from codewatch.checks.js_dead_code import check_js_dead_code
from codewatch.checks.js_tests import check_js_test_presence
from codewatch.checks.js_docstrings import check_js_docstrings

__all__ = [
    "check_complexity",
    "check_dead_code",
    "check_secrets",
    "check_test_presence",
    "check_docstrings",
    "check_js_secrets",
    "check_js_complexity",
    "check_js_dead_code",
    "check_js_test_presence",
    "check_js_docstrings",
]
