import itertools
import os

import dotenv
import pytest
from github import Issue

from src.babel_validation.sources.github.github_issues_test_cases import GitHubIssuesTestCases
from src.babel_validation.services.nameres import CachedNameRes
from src.babel_validation.services.nodenorm import CachedNodeNorm
from src.babel_validation.core.testrow import TestResult, TestStatus

# Helper functions
def get_github_issue_id(github_issue: Issue.Issue):
    return f"{github_issue.repository.organization.name}/{github_issue.repository.name}#{github_issue.number}"

# Initialize the test.
dotenv.load_dotenv()
github_token = os.getenv('GITHUB_TOKEN')
github_issues_test_cases = GitHubIssuesTestCases(github_token, [
    'NCATSTranslator/Babel',                # https://github.com/NCATSTranslator/Babel
    'NCATSTranslator/NodeNormalization',    # https://github.com/NCATSTranslator/NodeNormalization
    'NCATSTranslator/NameResolution',       # https://github.com/NCATSTranslator/NameResolution
    'TranslatorSRI/babel-validation',       # https://github.com/TranslatorSRI/babel-validation
])

@pytest.mark.parametrize("github_issue", github_issues_test_cases.get_all_issues())
def test_github_issue(target_info, github_issue, selected_github_issues, subtests):
    # If github_issues is provided, we can skip all others.
    if selected_github_issues:
        # Check all three possible ways in which this issue might be specified.
        github_issue_matched = False
        for selected_github_issue in selected_github_issues:
            if '/' in selected_github_issue:
                github_issue_matched = (f"{github_issue.repository.organization.name}/{github_issue.repository.name}#{github_issue.number}" == selected_github_issue)
            elif '#' in selected_github_issue:
                github_issue_matched = (f"{github_issue.repository.name}#{github_issue.number}" == selected_github_issue)
            else:
                github_issue_matched = int(selected_github_issue) == github_issue.number
            if github_issue_matched:
                break

        if github_issue_matched:
            # This issue is one of those that should be tested.
            pass
        else:
            pytest.skip(f"GitHub Issue {str(github_issue)} not included in list of GitHub issues to be tested: {selected_github_issues}.")
            return

    # Test this issue with NodeNorm.
    nodenorm = CachedNodeNorm.from_url(target_info['NodeNormURL'])
    nameres = CachedNameRes.from_url(target_info['NameResURL'])
    tests = github_issues_test_cases.get_test_issues_from_issue(github_issue)
    if not tests:
        pytest.skip(f"No tests found in issue {github_issue}")
        return

    issue_id = get_github_issue_id(github_issue)
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
