import itertools

import pytest

from src.babel_validation.services.nameres import CachedNameRes
from src.babel_validation.services.nodenorm import CachedNodeNorm
from src.babel_validation.core.testrow import TestResult, TestStatus


def test_github_issue(request, target_info, github_issue, github_issues_test_cases_fixture, subtests):
    nodenorm = CachedNodeNorm.from_url(target_info['NodeNormURL'])
    nameres = CachedNameRes.from_url(target_info['NameResURL'])
    tests = github_issues_test_cases_fixture.get_test_issues_from_issue(github_issue)
    if not tests:
        pytest.skip(f"No tests found in issue {github_issue}")
        return

    parts = github_issue.html_url.split('/')
    issue_id = f"{parts[3]}/{parts[4]}#{github_issue.number}"

    # Open issues are expected to have failing tests. Mark as xfail(strict=False) so
    # that failures show as XFAIL (x) and unexpected full passes show as XPASS (X).
    if github_issue.state == "open":
        request.node.add_marker(pytest.mark.xfail(
            reason=f"Issue {issue_id} is still open",
            strict=False,
        ))

    for test_issue in tests:
        results_nodenorm = test_issue.test_with_nodenorm(nodenorm)
        results_nameres = test_issue.test_with_nameres(nodenorm, nameres)

        for result in itertools.chain(results_nodenorm, results_nameres):
            with subtests.test(msg=issue_id):
                match result:
                    case TestResult(status=TestStatus.Passed, message=message):
                        assert True, f"{issue_id} ({github_issue.state}): {message}"

                    case TestResult(status=TestStatus.Failed, message=message):
                        assert False, f"{issue_id} ({github_issue.state}): {message}"

                    case TestResult(status=TestStatus.Skipped, message=message):
                        pytest.skip(f"{issue_id} ({github_issue.state}): {message}")

                    case _:
                        assert False, f"Unknown result from {issue_id}: {result}"
