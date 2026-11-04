"""Shared pytest fixtures."""

import pytest

from codewatch.diff import clear_line_number_cache


@pytest.fixture(autouse=True)
def _reset_diff_line_cache():
    clear_line_number_cache()
    yield
    clear_line_number_cache()