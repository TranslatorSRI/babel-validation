"""System tests for BabelTest trigger detection in GitHub issue bodies."""

from unittest.mock import MagicMock, patch
import pytest
import yaml

from src.babel_validation.core.testrow import TestStatus
from src.babel_validation.sources.github.github_issues_test_cases import GitHubIssuesTestCases

pytestmark = pytest.mark.unit

INVALID_NAME = "NotARealAssertion"


@pytest.fixture
def github_issues_test_cases():
    """Override the conftest fixture: these unit tests never hit the GitHub API,
    so build the parser with a dummy token rather than requiring GITHUB_TOKEN."""
    return GitHubIssuesTestCases("unit-test-dummy-token", ["test-org/test-repo"])


def _mock_issue(body: str, number: int = 999) -> MagicMock:
    """Minimal mock GitHub Issue for get_test_issues_from_issue()."""
    issue = MagicMock()
    issue.body = body
    issue.number = number
    issue.repository.full_name = "test-org/test-repo"
    return issue


class TestInvalidAssertionNameDetection:
    """Invalid assertion names are parsed but raise ValueError at execution time."""

    def _wiki_issue(self):
        return _mock_issue(f"{{{{BabelTest|{INVALID_NAME}|CHEBI:90926}}}}")

    def _yaml_issue(self):
        return _mock_issue(
            f"```yaml\nbabel_tests:\n  {INVALID_NAME}:\n  - CHEBI:90926\n```"
        )

    # --- parsing: invalid names are extracted, not rejected ---

    def test_wiki_syntax_parses_invalid_name(self, github_issues_test_cases):
        tests = github_issues_test_cases.get_test_issues_from_issue(self._wiki_issue())
        assert len(tests) == 1
        assert tests[0].assertion == INVALID_NAME

    def test_yaml_syntax_parses_invalid_name(self, github_issues_test_cases):
        tests = github_issues_test_cases.get_test_issues_from_issue(self._yaml_issue())
        assert len(tests) == 1
        assert tests[0].assertion == INVALID_NAME

    # --- execution: invalid names raise ValueError before any service call ---

    def test_wiki_invalid_name_raises_on_nodenorm(self, github_issues_test_cases):
        tests = github_issues_test_cases.get_test_issues_from_issue(self._wiki_issue())
        with pytest.raises(ValueError, match="Unknown assertion type"):
            list(tests[0].test_with_nodenorm(None))

    def test_wiki_invalid_name_raises_on_nameres(self, github_issues_test_cases):
        tests = github_issues_test_cases.get_test_issues_from_issue(self._wiki_issue())
        with pytest.raises(ValueError, match="Unknown assertion type"):
            list(tests[0].test_with_nameres(None, None))

    def test_yaml_invalid_name_raises_on_nodenorm(self, github_issues_test_cases):
        tests = github_issues_test_cases.get_test_issues_from_issue(self._yaml_issue())
        with pytest.raises(ValueError, match="Unknown assertion type"):
            list(tests[0].test_with_nodenorm(None))

    def test_yaml_invalid_name_raises_on_nameres(self, github_issues_test_cases):
        tests = github_issues_test_cases.get_test_issues_from_issue(self._yaml_issue())
        with pytest.raises(ValueError, match="Unknown assertion type"):
            list(tests[0].test_with_nameres(None, None))


@pytest.mark.unit
class TestTooManyParams:
    """Extra params for fixed-arity assertions should yield a failed result, not silently pass."""

    def _results(self, fixture, wiki_syntax, service="nodenorm"):
        mock = _mock_issue(wiki_syntax)
        tests = fixture.get_test_issues_from_issue(mock)
        assert len(tests) == 1
        if service == "nodenorm":
            return list(tests[0].test_with_nodenorm(MagicMock()))
        else:
            return list(tests[0].test_with_nameres(None, None))

    def test_haslabel_too_many_params(self, github_issues_test_cases):
        results = self._results(
            github_issues_test_cases,
            "{{BabelTest|HasLabel|CHEBI:15365|aspirin|unexpected}}"
        )
        assert len(results) == 1
        assert results[0].status == TestStatus.Failed
        assert "exactly two" in results[0].message

    def test_searchbyname_too_many_params(self, github_issues_test_cases):
        results = self._results(
            github_issues_test_cases,
            "{{BabelTest|SearchByName|water|CHEBI:15377|unexpected}}",
            service="nameres"
        )
        assert len(results) == 1
        assert results[0].status == TestStatus.Failed
        assert "exactly two" in results[0].message


@pytest.mark.unit
class TestTooFewParams:
    """Comparison assertions require 2+ CURIEs; a single CURIE must fail loudly,
    not pass (ResolvesWith) or fail (DoesNotResolveWith) vacuously."""

    def _results(self, fixture, wiki_syntax):
        mock = _mock_issue(wiki_syntax)
        tests = fixture.get_test_issues_from_issue(mock)
        assert len(tests) == 1
        return list(tests[0].test_with_nodenorm(MagicMock()))

    def test_resolveswith_single_curie_fails(self, github_issues_test_cases):
        results = self._results(
            github_issues_test_cases, "{{BabelTest|ResolvesWith|CHEBI:15365}}"
        )
        assert len(results) == 1
        assert results[0].status == TestStatus.Failed
        assert "at least two" in results[0].message

    def test_doesnotresolvewith_single_curie_fails(self, github_issues_test_cases):
        results = self._results(
            github_issues_test_cases, "{{BabelTest|DoesNotResolveWith|CHEBI:15365}}"
        )
        assert len(results) == 1
        assert results[0].status == TestStatus.Failed
        assert "at least two" in results[0].message


@pytest.mark.unit
class TestMalformedYaml:
    """A YAML block that matches the detection regex but is not valid YAML raises yaml.YAMLError."""

    MALFORMED_BODY = "```yaml\nbabel_tests:\n  Resolves:\n  - [unclosed bracket\n```"

    def test_malformed_yaml_raises(self, github_issues_test_cases):
        mock = _mock_issue(self.MALFORMED_BODY)
        with pytest.raises(yaml.YAMLError):
            github_issues_test_cases.get_test_issues_from_issue(mock)


@pytest.mark.unit
class TestEmptyOrNullBabelTests:
    """Documents behaviour when issue bodies contain empty or null babel test content."""

    # --- empty/null body (already handled gracefully) ---

    def test_none_body_returns_empty(self, github_issues_test_cases):
        mock = _mock_issue(None)
        assert github_issues_test_cases.get_test_issues_from_issue(mock) == []

    def test_whitespace_body_returns_empty(self, github_issues_test_cases):
        mock = _mock_issue("   ")
        assert github_issues_test_cases.get_test_issues_from_issue(mock) == []

    # --- wiki syntax: assertion name only, no curie params ---

    def test_wiki_no_curie_params_parsed(self, github_issues_test_cases):
        # {{BabelTest|Resolves}} with no params parses to an empty param_set, not a parse error.
        mock = _mock_issue("{{BabelTest|Resolves}}")
        tests = github_issues_test_cases.get_test_issues_from_issue(mock)
        assert len(tests) == 1
        assert tests[0].assertion == "Resolves"
        assert tests[0].param_sets == [[]]

    def test_wiki_needed_no_params(self, github_issues_test_cases):
        # {{BabelTest|Needed}} with no extra params is valid per the documented wiki syntax.
        mock = _mock_issue("{{BabelTest|Needed}}")
        tests = github_issues_test_cases.get_test_issues_from_issue(mock)
        assert len(tests) == 1
        assert tests[0].assertion == "Needed"
        assert tests[0].param_sets == [[]]

    # --- YAML syntax: null / empty values ---

    def test_yaml_null_babel_tests_raises(self, github_issues_test_cases):
        # babel_tests: null → ValueError with a clear message (null yaml value has no .items())
        mock = _mock_issue("```yaml\nbabel_tests:\n\n```")
        with pytest.raises(ValueError, match="no 'babel_tests' top-level key"):
            github_issues_test_cases.get_test_issues_from_issue(mock)

    def test_yaml_null_assertion_params_raises(self, github_issues_test_cases):
        # Resolves: null → ValueError with a clear message (null param list is a config error)
        mock = _mock_issue("```yaml\nbabel_tests:\n  Resolves:\n```")
        with pytest.raises(ValueError, match="null param list"):
            github_issues_test_cases.get_test_issues_from_issue(mock)

    def test_yaml_empty_assertion_params(self, github_issues_test_cases):
        # Resolves: [] → GitHubIssueTest with empty param_sets (no crash)
        mock = _mock_issue("```yaml\nbabel_tests:\n  Resolves: []\n```")
        tests = github_issues_test_cases.get_test_issues_from_issue(mock)
        assert len(tests) == 1
        assert tests[0].param_sets == []

    def test_yaml_scalar_assertion_params_treated_as_single_param_set(self, github_issues_test_cases):
        # Resolves: CHEBI:15365 (bare scalar) → wrapped as a single one-element param_set
        mock = _mock_issue("```yaml\nbabel_tests:\n  Resolves: CHEBI:15365\n```")
        tests = github_issues_test_cases.get_test_issues_from_issue(mock)
        assert len(tests) == 1
        assert tests[0].param_sets == [["CHEBI:15365"]]

    def test_yaml_babel_tests_as_list_raises(self, github_issues_test_cases):
        # babel_tests as a list (not a mapping) → clear ValueError, not an AttributeError on .items().
        mock = _mock_issue("```yaml\nbabel_tests:\n  - Resolves\n```")
        with pytest.raises(ValueError, match="must be a mapping"):
            github_issues_test_cases.get_test_issues_from_issue(mock)

    def test_yaml_non_string_assertion_name_raises(self, github_issues_test_cases):
        # A non-string assertion key (e.g. an integer) → clear ValueError, not a later
        # AttributeError when .lower() is called on the assertion name.
        mock = _mock_issue("```yaml\nbabel_tests:\n  123:\n  - CHEBI:15365\n```")
        with pytest.raises(ValueError, match="assertion name must be a string"):
            github_issues_test_cases.get_test_issues_from_issue(mock)


@pytest.mark.unit
class TestWikiMarkerCaseInsensitivity:
    """The {{BabelTest|...}} marker is case-insensitive, like assertion names."""

    @pytest.mark.parametrize("marker", ["BabelTest", "babeltest", "BABELTEST", "Babeltest"])
    def test_wiki_marker_any_case_parsed(self, github_issues_test_cases, marker):
        mock = _mock_issue(f"{{{{{marker}|Resolves|CHEBI:15365}}}}")
        tests = github_issues_test_cases.get_test_issues_from_issue(mock)
        assert len(tests) == 1
        assert tests[0].assertion == "Resolves"
        assert tests[0].param_sets == [["CHEBI:15365"]]

    def test_wiki_marker_any_case_detected(self, github_issues_test_cases):
        assert github_issues_test_cases.issue_has_tests(
            _mock_issue("{{babeltest|Resolves|CHEBI:12345}}")
        ) is True


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
