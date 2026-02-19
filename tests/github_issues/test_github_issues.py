import itertools
import os

import dotenv
import pytest

from src.babel_validation.sources.github.github_issues_test_cases import GitHubIssueTest, GitHubIssuesTestCases
from src.babel_validation.services.nameres import CachedNameRes
from src.babel_validation.services.nodenorm import CachedNodeNorm
from src.babel_validation.core.testrow import TestResult, TestStatus

# Initialize the test.
dotenv.load_dotenv()
github_token = os.getenv('GITHUB_TOKEN')
github_issues_test_cases = GitHubIssuesTestCases(github_token, [
    'NCATSTranslator/Babel',                # https://github.com/NCATSTranslator/Babel
    'NCATSTranslator/NodeNormalization',    # https://github.com/NCATSTranslator/NodeNormalization
    'NCATSTranslator/NameResolution',       # https://github.com/NCATSTranslator/NameResolution
    'TranslatorSRI/babel-validation',       # https://github.com/TranslatorSRI/babel-validation
])

github_issue_tests = github_issues_test_cases.get_all_test_issues()

@pytest.mark.parametrize("github_issue_test", github_issue_tests)
def test_github_issue(target_info, github_issue_test: GitHubIssueTest, selected_github_issues):
    # If --issue is provided, skip assertions not belonging to matching issues.
    if selected_github_issues:
        github_issue_matched = False
        for selected_github_issue in selected_github_issues:
            if '/' in selected_github_issue:
                # e.g. "NCATSTranslator/Babel#637"
                github_issue_matched = (
                    f"{github_issue_test.repo_id}#{github_issue_test.github_issue.number}"
                    == selected_github_issue
                )
            elif '#' in selected_github_issue:
                # e.g. "Babel#637"
                repo_name = github_issue_test.repo_id.split('/')[-1] if '/' in github_issue_test.repo_id else github_issue_test.repo_id
                github_issue_matched = (
                    f"{repo_name}#{github_issue_test.github_issue.number}"
                    == selected_github_issue
                )
            else:
                # bare number, e.g. "637"
                github_issue_matched = int(selected_github_issue) == github_issue_test.github_issue.number
            if github_issue_matched:
                break

        if not github_issue_matched:
            pytest.skip(
                f"GitHub Issue {github_issue_test.repo_id}#{github_issue_test.github_issue.number} "
                f"not included in list of GitHub issues to be tested: {selected_github_issues}."
            )
            return

    nodenorm = CachedNodeNorm.from_url(target_info['NodeNormURL'])
    nameres = CachedNameRes.from_url(target_info['NameResURL'])

    results = itertools.chain(
        github_issue_test.test_with_nodenorm(nodenorm),
        github_issue_test.test_with_nameres(nodenorm, nameres),
    )

    issue_label = f"{github_issue_test.repo_id}#{github_issue_test.github_issue.number} ({github_issue_test.github_issue.state})"

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
