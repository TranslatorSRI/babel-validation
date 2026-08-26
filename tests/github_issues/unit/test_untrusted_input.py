"""Guards on the content of an issue body, which nobody reviews before we parse it."""

import logging
import time
from unittest.mock import MagicMock

import pytest
import yaml

from src.babel_validation.core.testrow import TestStatus
from tests.github_issues.unit._helpers import _mock_issue

pytestmark = pytest.mark.unit


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
