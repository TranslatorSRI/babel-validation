"""babel_validation.runner, the layer that runs issue assertions without pytest.

Fake NodeNorm and NameRes clients, so nothing touches the network. Everything is imported
from the top-level ``babel_validation`` package, so these also check that public surface.
"""

import pytest
import requests

from babel_validation import Assertion, IssueReport, ResultRecord, TestStatus, run_assertions, run_issue_tests

pytestmark = pytest.mark.unit


def _node(identifier, label="label", types=("biolink:SmallMolecule",)):
    return {"id": {"identifier": identifier, "label": label}, "type": list(types)}


class FakeNodeNorm:
    """Stands in for CachedNodeNorm, backed by a {curie: node} dict. Like the real one it
    caches, and ``requests`` records the CURIEs each uncached request would have sent."""

    def __init__(self, resolved=None):
        self.resolved = resolved or {}
        self.requests = []
        self._seen = set()

    def normalize_curies(self, curies, **kwargs):
        uncached = [c for c in curies if c not in self._seen]
        if uncached:
            self.requests.append(uncached)
            self._seen.update(uncached)
        return {c: self.resolved.get(c) for c in curies}

    def normalize_curie(self, curie, **kwargs):
        return self.normalize_curies([curie])[curie]

    def __str__(self):
        return "FakeNodeNorm"


class FakeNameRes:
    def __init__(self, results=None):
        self.results = results if results is not None else []

    def lookup(self, query, **kwargs):
        return self.results

    def __str__(self):
        return "FakeNameRes"


def _run(state, assertions, *, nodenorm, nameres=None):
    return run_assertions("org/repo#1", "https://example/1", state, assertions,
                          nodenorm=nodenorm, nameres=nameres or FakeNameRes())


def resolves():
    return FakeNodeNorm({"CHEBI:15365": _node("CHEBI:15365")})


def test_closed_issue_that_passes_is_left_alone():
    report = _run("closed", [Assertion("Resolves", [["CHEBI:15365"]])], nodenorm=resolves())
    assert report.all_passed and not report.reopened and not report.closeable


def test_closed_issue_that_fails_should_be_reopened():
    report = _run("closed", [Assertion("Resolves", [["CHEBI:15365"]])], nodenorm=FakeNodeNorm())
    assert report.has_failures and report.reopened and not report.closeable


def test_open_issue_that_passes_is_closeable():
    report = _run("open", [Assertion("Resolves", [["CHEBI:15365"]])], nodenorm=resolves())
    assert report.closeable and not report.reopened


def test_open_issue_that_fails_is_neither():
    report = _run("open", [Assertion("Resolves", [["CHEBI:15365"]])], nodenorm=FakeNodeNorm())
    assert report.has_failures and not report.closeable and not report.reopened


def test_unknown_assertion_is_recorded_not_run_and_blocks_closeable():
    report = _run("open", [Assertion("NotARealAssertion", [["CHEBI:1"]]),
                           Assertion("Resolves", [["CHEBI:15365"]])], nodenorm=resolves())
    assert report.unknown_assertions == ["NotARealAssertion"]
    assert report.all_passed and not report.closeable


def test_nothing_ran_is_not_closeable():
    report = _run("open", [], nodenorm=FakeNodeNorm())
    assert isinstance(report, IssueReport)
    assert (report.issue_id, report.url, report.is_open) == ("org/repo#1", "https://example/1", True)
    assert not report.closeable


def test_every_result_names_its_assertion_and_each_assertion_is_one_request():
    nodenorm = FakeNodeNorm({"CHEBI:1": _node("CHEBI:1"), "CHEBI:2": _node("CHEBI:2")})
    report = _run("closed", [Assertion("Resolves", [["CHEBI:1"], ["CHEBI:2"]])], nodenorm=nodenorm)
    assert [(type(r), r.assertion, r.status) for r in report.results] == [
        (ResultRecord, "Resolves", TestStatus.Passed)] * 2
    assert len(nodenorm.requests) == 1, "the param_sets of one assertion should share a request"


def test_needed_fails_once_however_many_param_sets():
    report = _run("open", [Assertion("Needed", [["a"], ["b"], ["c"]])], nodenorm=FakeNodeNorm())
    # Once against each service, as the pytest suite has always counted it.
    assert [r.message for r in report.failed_results] == ["Test needed for issue"] * 2


def test_search_by_name_runs_against_nameres():
    nodenorm = FakeNodeNorm({"CHEBI:15377": _node("CHEBI:15377", "water")})
    report = _run("closed", [Assertion("SearchByName", [["water", "CHEBI:15377"]])],
                  nodenorm=nodenorm, nameres=FakeNameRes([{"curie": "CHEBI:15377"}]))
    assert report.all_passed


def test_a_service_error_propagates_rather_than_becoming_a_result():
    class DownNodeNorm(FakeNodeNorm):
        def normalize_curies(self, curies, **kwargs):
            raise requests.ConnectionError("NodeNorm is down")

    with pytest.raises(requests.ConnectionError):
        _run("open", [Assertion("Resolves", [["CHEBI:15365"]])], nodenorm=DownNodeNorm())


def test_run_issue_tests_reports_each_issue(github_issues_test_cases, monkeypatch):
    from tests.github_issues.unit._helpers import _mock_issue

    open_issue = _mock_issue("{{BabelTest|Resolves|CHEBI:15365}}", number=1)
    open_issue.state = "open"
    closed_issue = _mock_issue("{{BabelTest|Resolves|CHEBI:404}}", number=2)
    closed_issue.state = "closed"
    monkeypatch.setattr(github_issues_test_cases, "get_issues_with_tests",
                        lambda repos=None: iter([open_issue, closed_issue]))

    reports = run_issue_tests(github_issues_test_cases, nodenorm=resolves(), nameres=FakeNameRes())
    assert [(r.issue_id, r.closeable, r.reopened) for r in reports] == [
        ("test-org/test-repo#1", True, False),
        ("test-org/test-repo#2", False, True),
    ]
