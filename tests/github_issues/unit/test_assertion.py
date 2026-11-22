"""The Assertion object a parsed issue turns into, for tools other than this test suite."""

import pickle

import pytest
import yaml

from babel_validation.sources.github.github_issues_test_cases import Assertion, GitHubIssueTest
from tests.github_issues.unit._helpers import _mock_issue

pytestmark = pytest.mark.unit


def test_parsed_assertion_carries_plain_issue_metadata(github_issues_test_cases):
    issue = _mock_issue("{{BabelTest|Resolves|CHEBI:15365}}", number=42)
    issue.state = "closed"
    [assertion] = github_issues_test_cases.get_test_issues_from_issue(issue)

    assert (assertion.issue_id, assertion.issue_url, assertion.issue_state) == (
        "test-org/test-repo#42", "https://github.com/test-org/test-repo/issues/42", "closed")
    assert not hasattr(assertion, "github_issue"), "an Assertion must not hold the PyGithub Issue"


def test_assertion_pickles_and_builds_without_an_issue():
    assertion = Assertion("HasLabel", [["CHEBI:15365", "aspirin"]], issue_id="org/repo#1", issue_state="open")
    copy = pickle.loads(pickle.dumps(assertion))
    assert (copy.assertion, copy.param_sets, copy.issue_id, copy.issue_state) == (
        "HasLabel", [["CHEBI:15365", "aspirin"]], "org/repo#1", "open")
    assert str(copy) == "org/repo#1: HasLabel(1 param sets)"


def test_is_known():
    assert Assertion("resolves").is_known
    assert not Assertion("NotARealAssertion").is_known


def test_old_name_still_works():
    assert GitHubIssueTest is Assertion


def test_parse_babel_tests_reads_text_as_an_issue_body_is_read(github_issues_test_cases):
    """A local draft gets the same parse as the issue it will become."""
    from babel_validation.sources.github.github_issues_test_cases import parse_babel_tests

    body = (
        "{{BabelTest|Resolves|CHEBI:15365}}\n\n"
        "```yaml\nbabel_tests:\n  HasLabel:\n  - ['CHEBI:15365', aspirin]\n```\n"
    )
    from_text = parse_babel_tests(body, source_id="draft.md")
    from_issue = github_issues_test_cases.get_test_issues_from_issue(_mock_issue(body))
    assert [(a.assertion, a.param_sets) for a in from_text] == [(a.assertion, a.param_sets) for a in from_issue]
    assert [a.issue_id for a in from_text] == ["draft.md", "draft.md"]


@pytest.mark.parametrize("body, error, message", [
    ("```yaml\nbabel_tests:\n  Resolves: &a\n  - CHEBI:1\n  HasLabel: *a\n```", yaml.YAMLError, "aliases"),
    ("```yaml\nbabel_tests:\n  HasLabel:\n  - [CHEBI:1, NO]\n```", ValueError, "quote it"),
    ("x" * 65537, ValueError, "character body"),
])
def test_parse_babel_tests_keeps_the_issue_rules(body, error, message):
    from babel_validation.sources.github.github_issues_test_cases import parse_babel_tests

    with pytest.raises(error, match=message):
        parse_babel_tests(body, source_id="draft.md")
