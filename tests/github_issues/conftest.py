import os

import dotenv

from src.babel_validation.sources.github.github_issues_test_cases import GitHubIssuesTestCases

dotenv.load_dotenv()
_github_issues_test_cases = GitHubIssuesTestCases(os.getenv('GITHUB_TOKEN'), [
    'NCATSTranslator/Babel',
    'NCATSTranslator/NodeNormalization',
    'NCATSTranslator/NameResolution',
    'TranslatorSRI/babel-validation',
])


def pytest_generate_tests(metafunc):
    if "github_issue_test" not in metafunc.fixturenames:
        return
    selected_issues = metafunc.config.getoption('issue', default=[])
    if selected_issues:
        params = _github_issues_test_cases.get_specific_test_issues(selected_issues)
    else:
        params = _github_issues_test_cases.get_all_test_issues()
    metafunc.parametrize("github_issue_test", params)
