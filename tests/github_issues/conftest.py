import json
import os
import tempfile
from pathlib import Path

import dotenv
import pytest
from filelock import FileLock
from github import Issue

from src.babel_validation.sources.github.github_issues_test_cases import GitHubIssuesTestCases

dotenv.load_dotenv()
_github_token = os.getenv('GITHUB_TOKEN')
_repos = [
    'NCATSTranslator/Babel',
    'NCATSTranslator/NodeNormalization',
    'NCATSTranslator/NameResolution',
    'TranslatorSRI/babel-validation',
    'TranslatorSRI/babel-explorer',
]
github_issues_test_cases = None

_CACHE_FILE = Path(tempfile.gettempdir()) / "babel_validation_issues_cache.json"
_LOCK_FILE = _CACHE_FILE.with_suffix(".lock")

# Module-level cache to avoid re-fetching issues already retrieved during collection.
_fetched_issues_cache: dict[str, Issue.Issue] = {}


def _get_github_issues_test_cases() -> GitHubIssuesTestCases:
    """Lazily construct GitHubIssuesTestCases, skipping tests if no token is available."""
    global github_issues_test_cases
    if github_issues_test_cases is not None:
        return github_issues_test_cases
    if not _github_token:
        pytest.skip(
            "GITHUB_TOKEN environment variable not set; skipping GitHub issues tests.",
            allow_module_level=True,
        )
    github_issues_test_cases = GitHubIssuesTestCases(_github_token, _repos)
    return github_issues_test_cases


def _issue_id(issue: Issue.Issue) -> str:
    """Derive a test ID from an issue without making extra API calls."""
    parts = issue.html_url.split('/')
    return f"{parts[3]}/{parts[4]}#{issue.number}"


def _get_all_test_issue_ids() -> list[str]:
    """Return IDs of all issues that contain tests, using a file-based cache."""
    with FileLock(_LOCK_FILE):
        if _CACHE_FILE.exists():
            try:
                return json.loads(_CACHE_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                _CACHE_FILE.unlink(missing_ok=True)
        issues = list(_get_github_issues_test_cases().get_issues_with_tests())
        ids = [_issue_id(i) for i in issues]
        for issue, id_ in zip(issues, ids):
            _fetched_issues_cache[id_] = issue
        _CACHE_FILE.write_text(json.dumps(ids))
        return ids


def pytest_generate_tests(metafunc):
    if "github_issue_id" not in metafunc.fixturenames:
        return
    issue_id_filter = metafunc.config.getoption("issue", default=[])
    if issue_id_filter:
        issues = _get_github_issues_test_cases().get_issues_by_ids(issue_id_filter)
        ids = [_issue_id(i) for i in issues]
        for issue, id_ in zip(issues, ids):
            _fetched_issues_cache[id_] = issue
    else:
        ids = _get_all_test_issue_ids()
    metafunc.parametrize("github_issue_id", ids, ids=ids)


@pytest.fixture
def github_issue(github_issue_id):
    """Hydrate a GitHub Issue object from its string ID."""
    if github_issue_id in _fetched_issues_cache:
        return _fetched_issues_cache[github_issue_id]
    return _get_github_issues_test_cases().get_issues_by_ids([github_issue_id])[0]


@pytest.fixture(scope="session")
def github_issues_test_cases_fixture():
    return _get_github_issues_test_cases()
