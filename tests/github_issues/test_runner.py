"""Unit tests for babel_validation.runner — the pytest-independent report layer.

These use fake NodeNorm/NameRes clients (no network) and construct Assertion objects directly,
which is now trivial because Assertion stores only plain fields. They also import everything
through the public ``babel_validation`` API, so they double as an import-surface smoke test.
"""

import pytest

from babel_validation import (
    Assertion,
    IssueReport,
    ResultRecord,
    TestStatus,
    run_assertions,
)

pytestmark = pytest.mark.unit


def _node(identifier, label="label", types=("biolink:SmallMolecule",)):
    return {"id": {"identifier": identifier, "label": label}, "type": list(types)}


class FakeNodeNorm:
    """Minimal stand-in for CachedNodeNorm backed by a {curie: node|None} dict."""

    def __init__(self, resolved=None):
        self.resolved = resolved or {}

    def normalize_curies(self, curies, **kwargs):
        return {c: self.resolved.get(c) for c in curies}

    def normalize_curie(self, curie, **kwargs):
        return self.resolved.get(curie)

    def __str__(self):
        return "FakeNodeNorm"


class FakeNameRes:
    """Minimal stand-in for CachedNameRes returning a fixed lookup result list."""

    def __init__(self, results=None):
        self.results = results if results is not None else []

    def lookup(self, query, **kwargs):
        return self.results

    def __str__(self):
        return "FakeNameRes"


def _run(state, assertions, *, nodenorm, nameres=None):
    return run_assertions(
        "org/repo#1", "https://example/1", state, assertions,
        nodenorm=nodenorm, nameres=nameres or FakeNameRes(),
    )


# --- classification: open vs closed -----------------------------------------

def test_closed_all_pass_is_not_reopened():
    a = Assertion("Resolves", [["CHEBI:15365"]], issue_state="closed")
    report = _run("closed", [a], nodenorm=FakeNodeNorm({"CHEBI:15365": _node("CHEBI:15365")}))
    assert report.all_passed
    assert not report.has_failures
    assert not report.reopened
    assert not report.closeable


def test_closed_failure_is_reopened():
    a = Assertion("Resolves", [["CHEBI:15365"]], issue_state="closed")
    report = _run("closed", [a], nodenorm=FakeNodeNorm({}))  # CHEBI unresolved
    assert report.has_failures
    assert report.reopened
    assert not report.closeable


def test_open_all_pass_is_closeable():
    a = Assertion("Resolves", [["CHEBI:15365"]], issue_state="open")
    report = _run("open", [a], nodenorm=FakeNodeNorm({"CHEBI:15365": _node("CHEBI:15365")}))
    assert report.closeable
    assert report.all_passed
    assert not report.reopened


def test_open_failure_is_neither_closeable_nor_reopened():
    a = Assertion("Resolves", [["CHEBI:15365"]], issue_state="open")
    report = _run("open", [a], nodenorm=FakeNodeNorm({}))
    assert report.has_failures
    assert not report.closeable
    assert not report.reopened


# --- unknown assertions ------------------------------------------------------

def test_unknown_assertion_recorded_not_run():
    a = Assertion("NotARealAssertion", [["CHEBI:1"]], issue_state="open")
    report = _run("open", [a], nodenorm=FakeNodeNorm())
    assert report.unknown_assertions == ["NotARealAssertion"]
    assert report.results == []
    # An unknown assertion blocks "closeable" even on an open issue with no failures.
    assert not report.closeable


# --- provenance: each result carries its param_set ---------------------------

def test_results_attributed_to_param_sets():
    a = Assertion("Resolves", [["CHEBI:1"], ["CHEBI:2"]], issue_state="closed")
    nn = FakeNodeNorm({"CHEBI:1": _node("CHEBI:1"), "CHEBI:2": _node("CHEBI:2")})
    report = _run("closed", [a], nodenorm=nn)
    assert [r.param_set for r in report.results] == [["CHEBI:1"], ["CHEBI:2"]]
    assert all(isinstance(r, ResultRecord) and r.assertion == "Resolves" for r in report.results)
    assert all(r.status == TestStatus.Passed for r in report.results)


# --- NameRes path executes through run() -------------------------------------

def test_searchbyname_runs_against_nameres():
    a = Assertion("SearchByName", [["water", "CHEBI:15377"]], issue_state="closed")
    nn = FakeNodeNorm({"CHEBI:15377": _node("CHEBI:15377", "water")})
    nr = FakeNameRes([{"curie": "CHEBI:15377"}])
    report = _run("closed", [a], nodenorm=nn, nameres=nr)
    assert report.all_passed
    assert report.results[0].param_set == ["water", "CHEBI:15377"]


def test_report_is_an_issue_report_with_metadata():
    report = _run("open", [], nodenorm=FakeNodeNorm())
    assert isinstance(report, IssueReport)
    assert report.issue_id == "org/repo#1"
    assert report.url == "https://example/1"
    assert report.is_open
    # No assertions ⇒ no results ⇒ not closeable (nothing actually passed).
    assert not report.closeable
