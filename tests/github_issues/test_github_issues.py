import itertools

import pytest

from src.babel_validation.sources.github.github_issues_test_cases import GitHubIssueTest
from src.babel_validation.services.nameres import CachedNameRes
from src.babel_validation.services.nodenorm import CachedNodeNorm
from src.babel_validation.core.testrow import TestResult, TestStatus


def test_github_issue(target_info, github_issue_test: GitHubIssueTest):
    nodenorm = CachedNodeNorm.from_url(target_info['NodeNormURL'])
    nameres = CachedNameRes.from_url(target_info['NameResURL'])

    results = itertools.chain(
        github_issue_test.test_with_nodenorm(nodenorm),
        github_issue_test.test_with_nameres(nodenorm, nameres),
    )

    issue_label = (
        f"{github_issue_test.repo_id}#{github_issue_test.github_issue.number}"
        f" ({github_issue_test.github_issue.state})"
    )

    for result in results:
        match result:
            case TestResult(status=TestStatus.Passed, message=message):
                assert True, f"{issue_label}: {message}"
            case TestResult(status=TestStatus.Failed, message=message):
                assert False, f"{issue_label}: {message}"
            case TestResult(status=TestStatus.Skipped, message=message):
                pytest.skip(f"{issue_label}: {message}")
            case _:
                assert False, f"Unknown result from {issue_label}: {result}"
