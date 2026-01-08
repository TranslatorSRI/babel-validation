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

@pytest.mark.parametrize("test_issue", github_issues_test_cases.get_test_issues())
def test_github_issue_testrow(target_info, test_issue):
    print(f"Test issue: {test_issue}")

    nodenorm = CachedNodeNorm(target_info['NodeNormURL'])
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