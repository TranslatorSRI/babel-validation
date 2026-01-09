import os

import dotenv
import pytest

from tests.common.github_issues_test_cases import GitHubIssuesTestCases, CachedNodeNorm
from tests.common.testrow import TestResult, TestStatus

# Initialize the test.
dotenv.load_dotenv()
github_token = os.getenv('GITHUB_TOKEN')
github_issues_test_cases = GitHubIssuesTestCases(github_token, [
    'NCATSTranslator/Babel',                # https://github.com/NCATSTranslator/Babel
    'NCATSTranslator/NodeNormalization',    # https://github.com/NCATSTranslator/NodeNormalization
    'NCATSTranslator/NameResolution',       # https://github.com/NCATSTranslator/NameResolution
    'TranslatorSRI/babel-validation',       # https://github.com/TranslatorSRI/babel-validation
])

@pytest.mark.parametrize("issue", github_issues_test_cases.get_all_issues())
def test_github_issue_testrow(target_info, issue):
    nodenorm = CachedNodeNorm.for_url(target_info['NodeNormURL'])

    print(f"Issue: {issue}")

    test_issues = github_issues_test_cases.get_test_issues_from_issue(issue)
    if not test_issues:
        pytest.skip(f"No tests found for issue {issue}.")
        return

    for test_issue in test_issues:
        results = test_issue.test_with_nodenorm(nodenorm)

        for result in results:
            match result:
                case TestResult(status=TestStatus.Passed, message=message):
                    assert True, message
                case TestResult(status=TestStatus.Failed, message=message):
                    assert False, message
                case TestResult(status=TestStatus.Skipped, message=message):
                    pytest.skip(message)
                case _:
                    assert False, f"Unknown result: {result}"
