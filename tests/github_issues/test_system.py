"""System tests for BabelTest trigger detection in GitHub issue bodies."""

from unittest.mock import MagicMock
import pytest

from src.babel_validation.core.testrow import TestStatus

pytestmark = pytest.mark.unit

INVALID_NAME = "NotARealAssertion"


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

    def test_wiki_syntax_parses_invalid_name(self, github_issues_test_cases_fixture):
        tests = github_issues_test_cases_fixture.get_test_issues_from_issue(self._wiki_issue())
        assert len(tests) == 1
        assert tests[0].assertion == INVALID_NAME

    def test_yaml_syntax_parses_invalid_name(self, github_issues_test_cases_fixture):
        tests = github_issues_test_cases_fixture.get_test_issues_from_issue(self._yaml_issue())
        assert len(tests) == 1
        assert tests[0].assertion == INVALID_NAME

    # --- execution: invalid names raise ValueError before any service call ---

    def test_wiki_invalid_name_raises_on_nodenorm(self, github_issues_test_cases_fixture):
        tests = github_issues_test_cases_fixture.get_test_issues_from_issue(self._wiki_issue())
        with pytest.raises(ValueError, match="Unknown assertion type"):
            list(tests[0].test_with_nodenorm(None))

    def test_wiki_invalid_name_raises_on_nameres(self, github_issues_test_cases_fixture):
        tests = github_issues_test_cases_fixture.get_test_issues_from_issue(self._wiki_issue())
        with pytest.raises(ValueError, match="Unknown assertion type"):
            list(tests[0].test_with_nameres(None, None))

    def test_yaml_invalid_name_raises_on_nodenorm(self, github_issues_test_cases_fixture):
        tests = github_issues_test_cases_fixture.get_test_issues_from_issue(self._yaml_issue())
        with pytest.raises(ValueError, match="Unknown assertion type"):
            list(tests[0].test_with_nodenorm(None))

    def test_yaml_invalid_name_raises_on_nameres(self, github_issues_test_cases_fixture):
        tests = github_issues_test_cases_fixture.get_test_issues_from_issue(self._yaml_issue())
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

    def test_haslabel_too_many_params(self, github_issues_test_cases_fixture):
        results = self._results(
            github_issues_test_cases_fixture,
            "{{BabelTest|HasLabel|CHEBI:15365|aspirin|unexpected}}"
        )
        assert len(results) == 1
        assert results[0].status == TestStatus.Failed
        assert "exactly two" in results[0].message

    def test_searchbyname_too_many_params(self, github_issues_test_cases_fixture):
        results = self._results(
            github_issues_test_cases_fixture,
            "{{BabelTest|SearchByName|water|CHEBI:15377|unexpected}}",
            service="nameres"
        )
        assert len(results) == 1
        assert results[0].status == TestStatus.Failed
        assert "exactly two" in results[0].message
