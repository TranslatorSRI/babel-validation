import os

import dotenv
import pytest
from github import Issue

from src.babel_validation.sources.github.github_issues_test_cases import GitHubIssuesTestCases

dotenv.load_dotenv()
_github_token = os.getenv('GITHUB_TOKEN')
_repos = [
    'NCATSTranslator/Babel',
    'NCATSTranslator/NodeNormalization',
    'NCATSTranslator/NameResolution',
    'TranslatorSRI/babel-validation',
]
github_issues_test_cases = GitHubIssuesTestCases(_github_token, _repos)


def _issue_id(issue: Issue.Issue) -> str:
    """Derive a test ID from an issue without making extra API calls."""
    parts = issue.html_url.split('/')
    return f"{parts[3]}/{parts[4]}#{issue.number}"


def pytest_generate_tests(metafunc):
    if "github_issue" not in metafunc.fixturenames:
        return
    issue_ids = metafunc.config.getoption("issue", default=[])
    if issue_ids:
        # Fast path: direct API call for each named issue (near-instant)
        issues = github_issues_test_cases.get_issues_by_ids(issue_ids)
    else:
        # Standard path: fetch all, pre-filter to issues that have tests
        issues = [i for i in github_issues_test_cases.get_all_issues()
                  if github_issues_test_cases.issue_has_tests(i)]
    metafunc.parametrize("github_issue", issues, ids=[_issue_id(i) for i in issues])


@pytest.fixture(scope="session")
def github_issues_test_cases_fixture():
    return github_issues_test_cases
