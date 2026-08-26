"""Finding issues that carry tests, identifying them, and resolving an ID to one."""

from unittest.mock import MagicMock, patch

import pytest
from github import UnknownObjectException

from src.babel_validation.sources.github.github_issues_test_cases import GitHubIssuesTestCases, issue_id
from tests.github_issues.unit._helpers import _mock_issue

pytestmark = pytest.mark.unit


@pytest.mark.unit
class TestIssueHasTests:
    """Documents issue_has_tests() behaviour for various body contents."""

    def test_none_body_returns_false(self, github_issues_test_cases):
        assert github_issues_test_cases.issue_has_tests(_mock_issue(None)) is False

    def test_whitespace_body_returns_false(self, github_issues_test_cases):
        assert github_issues_test_cases.issue_has_tests(_mock_issue("   ")) is False

    def test_wiki_syntax_detected(self, github_issues_test_cases):
        assert github_issues_test_cases.issue_has_tests(
            _mock_issue("{{BabelTest|Resolves|CHEBI:12345}}")
        ) is True

    def test_yaml_syntax_detected(self, github_issues_test_cases):
        assert github_issues_test_cases.issue_has_tests(
            _mock_issue("```yaml\nbabel_tests:\n  Resolves:\n  - CHEBI:12345\n```")
        ) is True

    def test_plain_text_not_detected(self, github_issues_test_cases):
        assert github_issues_test_cases.issue_has_tests(
            _mock_issue("Just some text without babel tests.")
        ) is False


@pytest.mark.unit
class TestGetIssuesWithTests:
    """Documents the search-API path of get_issues_with_tests()."""

    _REPOS = ["test-org/test-repo"]

    def test_no_results_yields_nothing(self, github_issues_test_cases):
        with patch.object(github_issues_test_cases.github, "search_issues",
                          return_value=[]):
            results = list(
                github_issues_test_cases.get_issues_with_tests(self._REPOS)
            )
        assert results == []

    def test_matching_issue_is_yielded(self, github_issues_test_cases):
        mock = _mock_issue("{{BabelTest|Resolves|CHEBI:12345}}", number=1)
        # Two keyword searches per repo; first returns our issue, second returns nothing.
        with patch.object(github_issues_test_cases.github, "search_issues",
                          side_effect=[[mock], []]):
            results = list(
                github_issues_test_cases.get_issues_with_tests(self._REPOS)
            )
        assert results == [mock]

    def test_duplicate_across_keywords_deduplicated(self, github_issues_test_cases):
        # Issue contains both syntaxes → appears in both keyword searches → yielded once.
        body = (
            "{{BabelTest|Resolves|CHEBI:12345}}\n"
            "```yaml\nbabel_tests:\n  Resolves:\n  - CHEBI:12345\n```"
        )
        mock = _mock_issue(body, number=42)
        with patch.object(github_issues_test_cases.github, "search_issues",
                          side_effect=[[mock], [mock]]):
            results = list(
                github_issues_test_cases.get_issues_with_tests(self._REPOS)
            )
        assert results == [mock]

    def test_search_false_positive_filtered(self, github_issues_test_cases):
        # GitHub returns an issue that mentions the keyword in prose (no real BabelTest block).
        mock = _mock_issue("This issue discusses babel_tests: in passing.", number=99)
        with patch.object(github_issues_test_cases.github, "search_issues",
                          side_effect=[[mock], []]):
            results = list(
                github_issues_test_cases.get_issues_with_tests(self._REPOS)
            )
        assert results == []


@pytest.mark.unit
class TestIssueId:
    """issue_id() reads html_url, because issue.repository costs two extra REST
    calls for an issue that came out of the search API."""

    def test_id_built_from_html_url(self):
        issue = MagicMock()
        issue.number = 42
        issue.html_url = "https://github.com/test-org/test-repo/issues/42"
        assert issue_id(issue) == "test-org/test-repo#42"

    def test_repository_attribute_is_never_touched(self):
        # Accessing .repository on a search result triggers the extra fetches we
        # are avoiding, so the helper must not read it even when it is available.
        issue = MagicMock()
        issue.number = 7
        issue.html_url = "https://github.com/other-org/other-repo/issues/7"
        type(issue).repository = property(
            lambda self: pytest.fail("issue_id() must not read .repository")
        )
        assert issue_id(issue) == "other-org/other-repo#7"


@pytest.mark.unit
class TestGetIssuesByIdsNotFound:
    """A missing issue reaches the friendly ValueError in every supported ID
    format, rather than escaping as a raw PyGitHub 404 out of collection."""

    _REPOS = ["test-org/test-repo"]

    def _missing(self, fixture):
        repo = MagicMock()
        repo.get_issue.side_effect = UnknownObjectException(404, {"message": "Not Found"}, {})
        return patch.object(fixture.github, "get_repo", return_value=repo)

    @pytest.fixture
    def fixture(self):
        return GitHubIssuesTestCases("unit-test-dummy-token", self._REPOS)

    @pytest.mark.parametrize("issue_ref", [
        "test-org/test-repo#99999",   # org/repo#N
        "test-repo#99999",            # repo#N
        "99999",                      # N
    ])
    def test_missing_issue_raises_value_error(self, fixture, issue_ref):
        with self._missing(fixture):
            with pytest.raises(ValueError, match="Could not resolve issue ID"):
                fixture.get_issues_by_ids([issue_ref])

    def test_found_issue_is_returned(self, fixture):
        repo, issue = MagicMock(), MagicMock()
        repo.get_issue.return_value = issue
        with patch.object(fixture.github, "get_repo", return_value=repo):
            assert fixture.get_issues_by_ids(["test-org/test-repo#1"]) == [issue]

    def test_unparseable_id_raises_value_error(self, fixture):
        with pytest.raises(ValueError, match="Could not resolve issue ID"):
            fixture.get_issues_by_ids(["not-an-issue-reference"])


@pytest.mark.unit
class TestConfiguredRepositoriesOnly:
    """Assertions are executed from whatever issue body comes back, so an ID must never be able
    to point the run at a repository nobody configured."""

    @pytest.fixture
    def fixture(self):
        return GitHubIssuesTestCases("unit-test-dummy-token", ["test-org/test-repo"])

    @pytest.mark.parametrize("issue_ref", [
        "attacker/evil#1",                  # simply not configured
        "test-org/test-repo/../../evil#1",  # the repo group admits slashes: URL path injection
        "test-org/test-repo?x=y#1",
    ])
    def test_unconfigured_repo_is_never_fetched(self, fixture, issue_ref):
        with patch.object(fixture.github, "get_repo") as get_repo:
            with pytest.raises(ValueError, match="Could not resolve issue ID"):
                fixture.get_issues_by_ids([issue_ref])
            # The load-bearing half: without this the test would pass even if the check
            # landed after the fetch.
            get_repo.assert_not_called()
