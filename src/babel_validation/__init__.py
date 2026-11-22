"""babel_validation: validate Babel's outputs (NodeNorm and NameRes) against expectations.

The names below are the surface other repositories can rely on, for running the BabelTest
assertions written in GitHub issues:

- :class:`GitHubIssuesTestCases` finds the issues that carry BabelTests and parses them.
- :func:`parse_babel_tests` parses the same syntax from any text, such as a local draft.
- :class:`Assertion` is one parsed assertion: its name, its param_sets and where it came from.
  Run it against live services with ``run()``, or read ``assertion`` and ``param_sets`` to
  drive an executor of your own.
- :func:`run_issue_tests` and :func:`run_assertions` run them and return
  :class:`IssueReport` objects, which say which issues look closeable or due to be reopened.
- :class:`CachedNodeNorm` and :class:`CachedNameRes` are the caching service clients.
- :class:`TestResult` and :class:`TestStatus` are the result types.
"""

from babel_validation.core.testrow import TestResult, TestStatus
from babel_validation.runner import IssueReport, ResultRecord, run_assertions, run_issue_tests
from babel_validation.services.nameres import CachedNameRes
from babel_validation.services.nodenorm import CachedNodeNorm
from babel_validation.sources.github.github_issues_test_cases import (
    Assertion,
    GitHubIssuesTestCases,
    parse_babel_tests,
)

__all__ = [
    "Assertion",
    "CachedNameRes",
    "CachedNodeNorm",
    "GitHubIssuesTestCases",
    "IssueReport",
    "ResultRecord",
    "TestResult",
    "TestStatus",
    "parse_babel_tests",
    "run_assertions",
    "run_issue_tests",
]
