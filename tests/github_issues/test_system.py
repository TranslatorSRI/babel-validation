"""System tests for BabelTest trigger detection in GitHub issue bodies."""

import logging
import time
from unittest.mock import MagicMock, patch
import pytest
import yaml
from github import UnknownObjectException

from src.babel_validation.core.testrow import TestStatus
from src.babel_validation.sources.github.github_issues_test_cases import GitHubIssuesTestCases, issue_id

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
    issue.html_url = f"https://github.com/test-org/test-repo/issues/{number}"
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
            return list(tests[0].test_with_nameres(MagicMock(), MagicMock()))

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
class TestPaddedWikiSyntax:
    """Whitespace around a wiki assertion name is cosmetic, not an unknown assertion."""

    def test_padded_assertion_name_is_stripped(self, github_issues_test_cases):
        mock = _mock_issue("{{BabelTest| Resolves |CHEBI:15365}}")
        tests = github_issues_test_cases.get_test_issues_from_issue(mock)
        assert len(tests) == 1
        assert tests[0].assertion == "Resolves"

    def test_blank_assertion_name_raises(self, github_issues_test_cases):
        mock = _mock_issue("{{BabelTest|   |CHEBI:15365}}")
        with pytest.raises(ValueError, match="Missing assertion name"):
            github_issues_test_cases.get_test_issues_from_issue(mock)


@pytest.mark.unit
class TestNonStringYamlParams:
    """YAML 1.1 resolves bare `no`/`123`/`1.5` to non-strings; reject them at parse
    time rather than letting them reach param.strip()."""

    @pytest.mark.parametrize("literal, type_name", [
        ("123", "int"),
        ("no", "bool"),
        ("1.5", "float"),
    ])
    def test_non_string_param_raises(self, github_issues_test_cases, literal, type_name):
        mock = _mock_issue(f"```yaml\nbabel_tests:\n  HasLabel:\n  - [CHEBI:15365, {literal}]\n```")
        with pytest.raises(ValueError, match=f"expected a string, got {type_name}"):
            github_issues_test_cases.get_test_issues_from_issue(mock)

    def test_quoted_param_is_accepted(self, github_issues_test_cases):
        mock = _mock_issue("```yaml\nbabel_tests:\n  HasLabel:\n  - [CHEBI:15365, 'no']\n```")
        tests = github_issues_test_cases.get_test_issues_from_issue(mock)
        assert tests[0].param_sets == [["CHEBI:15365", "no"]]


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
class TestUntrustedInput:
    """Guards on issue bodies, which are untrusted input: anyone can write one, and nothing
    reviews it before we parse it and turn it into live API calls."""

    # --- denial of service ---

    def test_unterminated_yaml_block_is_fast(self, github_issues_test_cases):
        r"""Regression test for cubic backtracking in _BABELTEST_YAML_RE.

        The old pattern ended `\s+.*?\s+```, three nested backtracking quantifiers. A body that
        opens a babel_tests block and never closes the fence took 6.8s at 4KB and 53s at 8KB,
        extrapolating to hours at GitHub's 65536-character limit — and this runs during
        collection, which pytest-timeout does not cover, so one issue hung the entire run before
        a single test started. The budget is generous because what it catches is a difference
        between milliseconds and hours, not a slow regression.
        """
        mock = _mock_issue("```yaml\nbabel_tests:\n" + " " * 20000 + "x" * 20000)
        started = time.monotonic()
        assert github_issues_test_cases.issue_has_tests(mock) is False
        assert time.monotonic() - started < 1.0

    @pytest.mark.parametrize("body", [
        # Chained anchors: each level multiplies the one below it.
        "```yaml\nbabel_tests:\n  Resolves: &a [CHEBI:1,CHEBI:1,CHEBI:1]\n"
        "  B: &b [*a,*a,*a]\n  C: &c [*b,*b,*b]\n  D: [*c,*c,*c]\n```",
        # A merge key needs an alias, so refusing aliases covers it.
        "```yaml\nbabel_tests:\n  base: &b [CHEBI:1]\n  Resolves:\n    <<: *b\n```",
    ])
    def test_yaml_aliases_are_rejected(self, github_issues_test_cases, body):
        """safe_load blocks code execution but still expands aliases, and PyYAML shares the
        aliased nodes — so the load looks cheap and the cost lands on whatever stringifies the
        result. A 337-byte body of chained anchors reached 25 MB in an error message."""
        with pytest.raises(yaml.YAMLError, match="anchors/aliases"):
            github_issues_test_cases.get_test_issues_from_issue(_mock_issue(body))

    def test_inline_yaml_mention_is_not_a_test_block(self, github_issues_test_cases):
        """A real fenced block always has a newline after `babel_tests:`, so anchoring on it
        keeps prose that merely *discusses* the syntax on one line from being picked up and
        then failing the issue — as happened to TranslatorSRI/babel-validation#100."""
        mock = _mock_issue("Write the header as ```yaml babel_tests: ``` and then the keys.")
        assert github_issues_test_cases.issue_has_tests(mock) is False
        assert github_issues_test_cases.get_test_issues_from_issue(mock) == []

    def test_deeply_nested_yaml_raises_value_error(self, github_issues_test_cases):
        """A few KB of nesting blows the interpreter stack inside the loader; report it as a
        malformed block rather than a several-thousand-frame traceback."""
        mock = _mock_issue("```yaml\nbabel_tests:\n  Resolves: " + "[" * 2000 + "]" * 2000 + "\n```")
        with pytest.raises(ValueError, match="nested too deeply"):
            github_issues_test_cases.get_test_issues_from_issue(mock)

    def test_duplicate_yaml_keys_are_rejected(self, github_issues_test_cases):
        """YAML says last-wins, which breaks the assumption the feature rests on: that a
        reviewer reading the body can see what the run will do."""
        mock = _mock_issue(
            "```yaml\nbabel_tests:\n  Resolves:\n  - CHEBI:15365\n  Resolves:\n  - CHEBI:99999\n```"
        )
        with pytest.raises(yaml.YAMLError, match="duplicate key"):
            github_issues_test_cases.get_test_issues_from_issue(mock)

    # --- size caps: the whole issue fails, so that it gets split up ---

    def test_oversized_body_raises(self, github_issues_test_cases):
        mock = _mock_issue("{{BabelTest|Resolves|CHEBI:15365}}" + "x" * 65536)
        with pytest.raises(ValueError, match="over the"):
            github_issues_test_cases.get_test_issues_from_issue(mock)

    @pytest.mark.parametrize("body, match", [
        ("{{BabelTest|Resolves|CHEBI:15365}}" * 101, "BabelTest assertions"),
        ("```yaml\nbabel_tests:\n  Resolves:\n" + "  - [CHEBI:15365]\n" * 1001 + "```", "param sets"),
        ("```yaml\nbabel_tests:\n  Resolves:\n  - [" + "CHEBI:1," * 1001 + "]\n```", "parameters"),
    ])
    def test_size_caps_raise(self, github_issues_test_cases, body, match):
        with pytest.raises(ValueError, match=match):
            github_issues_test_cases.get_test_issues_from_issue(_mock_issue(body))

    def test_oversized_body_is_still_collected(self, github_issues_test_cases):
        """issue_has_tests() runs during collection over every issue the search returned, so it
        claims an oversized body rather than raising — raising there would abort the whole run
        for one bad issue. get_test_issues_from_issue() then fails it on its own."""
        assert github_issues_test_cases.issue_has_tests(_mock_issue("x" * 65537)) is True

    def test_bad_assertion_name_raises(self, github_issues_test_cases):
        mock = _mock_issue("{{BabelTest|Resolves\x1b[31m|CHEBI:15365}}")
        with pytest.raises(ValueError, match="Invalid assertion name"):
            github_issues_test_cases.get_test_issues_from_issue(mock)

    # --- per-param problems: only the offending param_set fails ---

    def test_over_long_param_fails_only_its_own_param_set(self, github_issues_test_cases):
        """The asymmetry that matters: structural caps fail the whole issue, but a bad param
        goes through the existing _rejection() path so its siblings still run."""
        mock = _mock_issue(
            "```yaml\nbabel_tests:\n  Resolves:\n  - ['CHEBI:" + "9" * 1001 + "']\n"
            "  - [CHEBI:15365]\n```"
        )
        tests = github_issues_test_cases.get_test_issues_from_issue(mock)
        nodenorm = MagicMock()
        nodenorm.normalize_curie.return_value = {"id": {"identifier": "CHEBI:15365"}}
        results = list(tests[0].test_with_nodenorm(nodenorm))

        failed = [r for r in results if r.status == TestStatus.Failed]
        assert len(failed) == 1, results
        # The rejected param never reaches NodeNorm, and the sibling param_set still runs.
        assert nodenorm.normalize_curies.call_args[0][0] == ["CHEBI:15365"]
        assert any(r.status == TestStatus.Passed for r in results), results
        # Truncated, so an enormous param cannot blow up the report it is kept in.
        assert len(failed[0].message) < 500

    @pytest.mark.parametrize("bad_param", [
        "\x1b[31mCHEBI:15365",   # ANSI escape
        "CHEBI:15365‮",     # bidi override
        "CHEBI:​15365",     # zero-width space
    ])
    def test_control_characters_in_wiki_param_are_rejected(self, github_issues_test_cases, bad_param):
        """Wiki syntax is the unguarded path for these: it is a plain str.split('|'), whereas
        YAML cannot carry a raw control character at all (see the test below)."""
        mock = _mock_issue("{{BabelTest|Resolves|" + bad_param + "}}")
        tests = github_issues_test_cases.get_test_issues_from_issue(mock)
        nodenorm = MagicMock()
        results = list(tests[0].test_with_nodenorm(nodenorm))

        assert [r.status for r in results] == [TestStatus.Failed], results
        assert "non-printable" in results[0].message
        # Never reaches the service...
        nodenorm.normalize_curies.assert_not_called()
        # ...and repr() escapes it, so it cannot reach an operator's terminal raw.
        assert not any(c in results[0].message for c in ("\x1b", "‮", "​"))

    def test_issue_text_is_escaped_in_the_logs(self, github_issues_test_cases, caplog):
        """The parser logs the matched text and the params before anything has validated them,
        so %r rather than %s is what keeps an escape sequence out of an operator's terminal.
        _rejection() runs much later and cannot help here."""
        mock = _mock_issue("{{BabelTest|Resolves|\x1b[31mCHEBI:15365}}")
        with caplog.at_level(logging.INFO):
            github_issues_test_cases.get_test_issues_from_issue(mock)

        # Assert on the records, not caplog.text: pytest does not carry a raw control
        # character through caplog.text, so asserting on it passes whatever the code does.
        messages = [r.getMessage() for r in caplog.records]
        assert messages, "nothing was logged, so the assertions below would be vacuous"
        assert not any("\x1b" in m for m in messages), messages
        # Present, just escaped — otherwise this would pass by not logging the text at all.
        assert any("\\x1b" in m for m in messages), messages

    def test_str_does_not_dump_param_sets(self, github_issues_test_cases):
        """str() of a test is the `label` on every TestResult it produces, so dumping the params
        into it repeated them once per message."""
        mock = _mock_issue("```yaml\nbabel_tests:\n  Resolves:\n  - [CHEBI:15365]\n  - [CHEBI:16480]\n```")
        label = str(github_issues_test_cases.get_test_issues_from_issue(mock)[0])
        assert "2 param sets" in label
        assert "CHEBI:15365" not in label

    def test_yaml_rejects_raw_control_characters(self, github_issues_test_cases):
        """PyYAML's reader refuses control characters in the stream, so the YAML syntax never
        reaches our own isprintable() check. Pinned so that stays true."""
        mock = _mock_issue("```yaml\nbabel_tests:\n  Resolves:\n  - ['\x1b[31m']\n```")
        with pytest.raises(yaml.YAMLError, match="special characters are not allowed"):
            github_issues_test_cases.get_test_issues_from_issue(mock)

    def test_empty_param_is_rejected(self, github_issues_test_cases):
        mock = _mock_issue("```yaml\nbabel_tests:\n  SearchByName:\n  - ['  ', CHEBI:15365]\n```")
        tests = github_issues_test_cases.get_test_issues_from_issue(mock)
        results = list(tests[0].test_with_nameres(MagicMock(), MagicMock()))
        assert [r.status for r in results] == [TestStatus.Failed]
        assert "is empty" in results[0].message


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
