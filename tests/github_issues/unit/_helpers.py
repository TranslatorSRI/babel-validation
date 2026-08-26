"""Shared helper for the offline GitHub-issue tests.

Not conftest.py: _mock_issue() is a plain function rather than a fixture, so it has to be
imported. The fixture that has to be discovered — the dummy-token override — lives next door.
"""

from unittest.mock import MagicMock


def _mock_issue(body: str, number: int = 999) -> MagicMock:
    """Minimal mock GitHub Issue for get_test_issues_from_issue()."""
    issue = MagicMock()
    issue.body = body
    issue.number = number
    issue.html_url = f"https://github.com/test-org/test-repo/issues/{number}"
    return issue
