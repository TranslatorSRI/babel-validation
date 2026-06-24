"""babel_validation — validate Babel (NodeNorm / NameRes) outputs against tests embedded in
GitHub issues.

Public API (stable surface for downstream consumers such as the Babel pipeline and Babel
Explorer):

- :class:`GitHubIssuesTestCases` — fetch + parse BabelTest assertions from GitHub issues.
- :class:`Assertion` — one parsed assertion (name + param_sets + issue metadata). Run it against
  live services with ``run()`` / ``test_with_*``, or read ``assertion``/``param_sets`` to drive
  your own executor (e.g. against a local database).
- :func:`run_issue_tests` / :func:`run_assertions` — run assertions and get
  :class:`IssueReport` objects (pass/fail messages + closeable/reopened classification).
- :class:`CachedNodeNorm` / :class:`CachedNameRes` — caching service clients.
- :class:`TestResult` / :class:`TestStatus` — the result value types.
"""

from babel_validation.core.testrow import TestResult, TestStatus
from babel_validation.runner import (
    IssueReport,
    ResultRecord,
    run_assertions,
    run_issue_tests,
)
from babel_validation.services.nameres import CachedNameRes
from babel_validation.services.nodenorm import CachedNodeNorm
from babel_validation.sources.github.github_issues_test_cases import (
    Assertion,
    GitHubIssuesTestCases,
)

__all__ = [
    "Assertion",
    "GitHubIssuesTestCases",
    "run_issue_tests",
    "run_assertions",
    "IssueReport",
    "ResultRecord",
    "CachedNodeNorm",
    "CachedNameRes",
    "TestResult",
    "TestStatus",
]
