import os

import dotenv
import pytest
from github import Issue

from tests.common.github_issues_test_cases import GitHubIssuesTestCases, CachedNodeNorm
from tests.common.testrow import TestResult, TestStatus

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
def test_github_issue(target_info, github_issue, selected_github_issues):
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

    # Test this issue.
    print(f"Testing issue {str(github_issue)}")
    nodenorm = CachedNodeNorm.from_url(target_info['NodeNormURL'])
    tests = github_issues_test_cases.get_test_issues_from_issue(github_issue)
    if not tests:
        pytest.skip(f"No tests found in issue {github_issue}")
        return

    for test_issue in tests:
        results = test_issue.test_with_nodenorm(nodenorm)

        for result in results:
            match result:
                case TestResult(status=TestStatus.Passed, message=message):
                    assert True, message
                case TestResult(status=TestStatus.Failed, message=message):
                    assert False, f"{get_github_issue_id(github_issue)}: {message}"
                case TestResult(status=TestStatus.Skipped, message=message):
                    pytest.skip(f"{get_github_issue_id(github_issue)}: {message}")
                case _:
                    assert False, f"Unknown result from {get_github_issue_id(github_issue)}: {result}"
