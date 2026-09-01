"""Fixtures for the offline GitHub-issue tests.

This directory exists for the override below. tests/github_issues/conftest.py defines a
session-scoped github_issues_test_cases that needs a real GITHUB_TOKEN and skips the module
without one; these tests want a dummy-token parser instead. Overriding it here scopes the
replacement to this directory, leaving the live test_github_issues.py on the real fixture —
which putting it in the parent conftest would not.
"""

import pytest

from src.babel_validation.sources.github.github_issues_test_cases import GitHubIssuesTestCases


@pytest.fixture
def github_issues_test_cases():
    """Override the parent conftest fixture: these unit tests never hit the GitHub API,
    so build the parser with a dummy token rather than requiring GITHUB_TOKEN."""
    return GitHubIssuesTestCases("unit-test-dummy-token", ["test-org/test-repo"])
