import itertools

import pytest
from github import Issue

from src.babel_validation.services.nameres import CachedNameRes
from src.babel_validation.services.nodenorm import CachedNodeNorm
from src.babel_validation.core.testrow import TestResult, TestStatus


def test_github_issue(target_info, github_issue, github_issues_test_cases_fixture, subtests):
    nodenorm = CachedNodeNorm.from_url(target_info['NodeNormURL'])
    nameres = CachedNameRes.from_url(target_info['NameResURL'])
    tests = github_issues_test_cases_fixture.get_test_issues_from_issue(github_issue)
    if not tests:
        pytest.skip(f"No tests found in issue {github_issue}")
        return

    parts = github_issue.html_url.split('/')
    issue_id = f"{parts[3]}/{parts[4]}#{github_issue.number}"
    subtests_passed = 0
    subtests_failed = 0

    for test_issue in tests:
        results_nodenorm = test_issue.test_with_nodenorm(nodenorm)
        results_nameres = test_issue.test_with_nameres(nodenorm, nameres)

        for result in itertools.chain(results_nodenorm, results_nameres):
            with subtests.test(msg=f"{issue_id} ({github_issue.state}): {result.message}"):
                match result:
                    case TestResult(status=TestStatus.Passed, message=message):
                        subtests_passed += 1
                        assert True, f"{issue_id} ({github_issue.state}): {message}"

                    case TestResult(status=TestStatus.Failed, message=message):
                        subtests_failed += 1
                        assert False, f"{issue_id} ({github_issue.state}): {message}"

                    case TestResult(status=TestStatus.Skipped, message=message):
                        pytest.skip(f"{issue_id} ({github_issue.state}): {message}")

                    case _:
                        subtests_failed += 1
                        assert False, f"Unknown result from {issue_id}: {result}"

    # Issue state vs. test results consistency checks
    if github_issue.state == "closed" and subtests_failed > 0:
        with subtests.test(msg=f"Issue state: {issue_id} is closed but has failing tests"):
            assert False, (
                f"Issue {issue_id} is closed but {subtests_failed} subtest(s) failed. "
                f"Consider reopening: {github_issue.html_url}"
            )

    if github_issue.state == "open" and subtests_passed > 0 and subtests_failed == 0:
        with subtests.test(msg=f"Issue state: {issue_id} is open but all tests pass"):
            pytest.xfail(
                f"Issue {issue_id} is open but all {subtests_passed} subtest(s) passed. "
                f"Consider closing: {github_issue.html_url}"
            )
