"""How test_github_issue reports an open issue: XFAIL, strict XPASS, or a real failure.

These run test_github_issue itself in an inner pytest session (pytester), with the issue,
its parsed assertions and the services replaced by fakes, because the outcome depends on
the xfail marker the test adds to its own node, which only a pytest run applies.
"""

import pytest

pytestmark = pytest.mark.unit

pytest_plugins = ["pytester"]

CONFTEST = '''
import pytest
import requests
from types import SimpleNamespace

from babel_validation.core.testrow import TestResult, TestStatus

BEHAVIOUR = {behaviour!r}


class FakeAssertion:
    assertion = "resolves"
    param_sets = [["MONDO:0005015"]]

    def test_with_nodenorm(self, nodenorm):
        if BEHAVIOUR == "raises":
            raise requests.ConnectionError("NodeNorm is down")
        status = TestStatus.Passed if BEHAVIOUR == "passes" else TestStatus.Failed
        return [TestResult(status=status, message=BEHAVIOUR)]

    def test_with_nameres(self, nodenorm, nameres, pass_if_found_in_top):
        return []


class FakeTestCases:
    def get_test_issues_from_issue(self, issue):
        return [FakeAssertion()]


@pytest.fixture
def target_info():
    return {{"NodeNormURL": "https://nodenorm.invalid/", "NameResURL": "https://nameres.invalid/"}}


@pytest.fixture
def github_issue_id():
    return "test-org/test-repo#1"


@pytest.fixture
def github_issue():
    return SimpleNamespace(state="open", html_url="https://github.com/test-org/test-repo/issues/1")


@pytest.fixture
def github_issues_test_cases():
    return FakeTestCases()
'''


@pytest.mark.parametrize(
    "behaviour, outcome",
    [
        # The expected state of an open issue.
        ("fails", {"xfailed": 1}),
        # Looks closeable: strict XPASS, reported as a failure.
        ("passes", {"failed": 1}),
        # An outage is not the issue's bug, so it must not read as XFAIL.
        ("raises", {"failed": 1}),
    ],
)
def test_open_issue_outcome(pytester, behaviour, outcome):
    pytester.makeconftest(CONFTEST.format(behaviour=behaviour))
    pytester.makepyfile(test_inner="from tests.github_issues.test_github_issues import test_github_issue\n")
    result = pytester.runpytest_inprocess("-p", "no:cacheprovider")
    result.assert_outcomes(**outcome)
