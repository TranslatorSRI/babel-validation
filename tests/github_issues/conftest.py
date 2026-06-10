import configparser
import json
import os
import tempfile
from pathlib import Path

import dotenv
import pytest
from filelock import FileLock
from github import GithubException, Issue

from src.babel_validation.sources.github.github_issues_test_cases import GitHubIssuesTestCases

_github_token = None
_github_auth_error: str | None = None

_AUTH_ERROR_ID = "github-auth-error"
_AUTH_HELP = (
    "GitHub token is expired or invalid. Generate a new one at "
    "https://github.com/settings/tokens and set it as the GITHUB_TOKEN "
    "environment variable (or in a .env file), then delete the cache file "
    f"at {Path(tempfile.gettempdir()) / 'babel_validation_issues_cache.json'} "
    "if it exists."
)

_targets_config = configparser.ConfigParser()
_targets_config.read(Path(__file__).parent.parent / 'targets.ini')
_repos = [
    r.strip()
    for r in _targets_config['DEFAULT']['Repositories'].splitlines()
    if r.strip()
]
_github_issues_test_cases = None

_CACHE_FILE = Path(tempfile.gettempdir()) / "babel_validation_issues_cache.json"
_LOCK_FILE = _CACHE_FILE.with_suffix(".lock")

# Module-level cache to avoid re-fetching issues already retrieved during collection.
_fetched_issues_cache: dict[str, Issue.Issue] = {}


def _get_github_issues_test_cases() -> GitHubIssuesTestCases:
    """Lazily construct GitHubIssuesTestCases, skipping tests if no token is available."""
    global _github_issues_test_cases, _github_token
    if _github_issues_test_cases is not None:
        return _github_issues_test_cases
    if _github_token is None:
        dotenv.load_dotenv()
        _github_token = os.getenv('GITHUB_TOKEN') or ''
    if not _github_token:
        pytest.skip(
            "GITHUB_TOKEN environment variable not set; skipping GitHub issues tests.",
            allow_module_level=True,
        )
    _github_issues_test_cases = GitHubIssuesTestCases(_github_token, _repos)
    return _github_issues_test_cases


def _issue_id(issue: Issue.Issue) -> str:
    """Derive a test ID from an issue without making extra API calls."""
    return f"{issue.repository.full_name}#{issue.number}"


def _record_auth_error(e: GithubException) -> None:
    global _github_auth_error
    _github_auth_error = f"{_AUTH_HELP}\n\nOriginal error: {e}"


_cached_ids: list[str] | None = None


def _get_all_test_issue_ids() -> list[str]:
    """Return IDs of all issues that contain tests, using a file-based cache."""
    global _cached_ids
    if _cached_ids is not None:
        return _cached_ids
    with FileLock(_LOCK_FILE):
        if _CACHE_FILE.exists():
            try:
                _cached_ids = json.loads(_CACHE_FILE.read_text())
                return _cached_ids
            except (json.JSONDecodeError, OSError):
                _CACHE_FILE.unlink(missing_ok=True)
        try:
            issues = list(_get_github_issues_test_cases().get_issues_with_tests())
        except GithubException as e:
            if e.status == 401:
                _record_auth_error(e)
                _cached_ids = [_AUTH_ERROR_ID]
                return _cached_ids
            raise
        ids = [_issue_id(i) for i in issues]
        for issue, id_ in zip(issues, ids):
            _fetched_issues_cache[id_] = issue
        _CACHE_FILE.write_text(json.dumps(ids))
        _cached_ids = ids
        return ids


def _deselected_by_markexpr(metafunc) -> bool:
    """True if a -m marker expression is active that would deselect this test.

    Parametrizing ``test_github_issue`` fetches issues from GitHub at collection
    time. When the user runs e.g. ``pytest -m unit`` that test is deselected
    anyway (it carries no ``unit`` marker), so we must avoid the network round
    trip. pytest only applies ``-m`` deselection *after* generation, so we
    evaluate the expression ourselves against the markers on the test.
    """
    markexpr = metafunc.config.getoption("markexpr")
    if not markexpr:
        return False
    try:
        from _pytest.mark.expression import Expression
    except ImportError:
        # Internal API moved; fall back to the (network-using) default.
        return False
    own_markers = {m.name for m in metafunc.definition.iter_markers()}
    try:
        return not Expression.compile(markexpr).evaluate(lambda name: name in own_markers)
    except Exception:
        # Unparseable expression — let pytest handle it; don't suppress tests.
        return False


def pytest_generate_tests(metafunc):
    if "github_issue_id" not in metafunc.fixturenames:
        return
    if _deselected_by_markexpr(metafunc):
        # Skip the GitHub fetch entirely; this test won't run under this -m filter.
        metafunc.parametrize("github_issue_id", [], ids=[])
        return
    issue_id_filter = metafunc.config.getoption("issue", default=[])
    if issue_id_filter:
        try:
            issues = _get_github_issues_test_cases().get_issues_by_ids(issue_id_filter)
        except GithubException as e:
            if e.status == 401:
                _record_auth_error(e)
                metafunc.parametrize("github_issue_id", [_AUTH_ERROR_ID], ids=[_AUTH_ERROR_ID])
                return
            raise
        ids = [_issue_id(i) for i in issues]
        for issue, id_ in zip(issues, ids):
            _fetched_issues_cache[id_] = issue
    else:
        ids = _get_all_test_issue_ids()
    metafunc.parametrize("github_issue_id", ids, ids=ids)


@pytest.fixture
def github_issue(github_issue_id):
    """Hydrate a GitHub Issue object from its string ID."""
    if github_issue_id == _AUTH_ERROR_ID:
        pytest.fail(_github_auth_error or _AUTH_HELP)
    if github_issue_id in _fetched_issues_cache:
        return _fetched_issues_cache[github_issue_id]
    try:
        return _get_github_issues_test_cases().get_issues_by_ids([github_issue_id])[0]
    except GithubException as e:
        if e.status == 401:
            pytest.fail(f"{_AUTH_HELP}\n\nOriginal error: {e}")
        raise


@pytest.fixture(scope="session")
def github_issues_test_cases():
    return _get_github_issues_test_cases()
