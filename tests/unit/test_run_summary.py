"""Unit tests for the end-of-run summary (summarize_run in tests/_pytest_helpers.py). No network."""

import configparser

import pytest

from tests._pytest_helpers import summarize_run

pytestmark = pytest.mark.unit


def _record(nodeid, outcome="passed", when="call", wasxfail=False):
    return {
        "id": nodeid,
        "when": when,
        "outcome": outcome,
        "wasxfail": wasxfail,
        "msg": None,
    }


def _sections():
    cp = configparser.ConfigParser()
    cp.read_string(
        "[dev]\nNodeNormURL = https://nn.dev/\nNameResURL = https://nr.dev/\n"
        "[ci-es]\nNodeNormURL = https://nn.ci-es/\nNameResURL = https://nr.ci-es/\n"
    )
    return {"dev": cp["dev"], "ci-es": cp["ci-es"]}


def test_summarize_run():
    gsheet = "tests/nodenorm/test_nodenorm_from_gsheet.py::test_normalization"
    records = [
        _record(f"{gsheet}[dev-gsheet:row=1]"),
        _record(f"{gsheet}[ci-es-gsheet:row=1]"),
        _record(f"{gsheet}[dev-gsheet:row=2]", "failed"),
        _record(f"{gsheet}[ci-es-gsheet:row=2]"),
        # Skipped by category filter: not counted towards the pass rate.
        _record(f"{gsheet}[dev-gsheet:row=3]", "skipped", when="setup"),
        _record(f"{gsheet}[ci-es-gsheet:row=3]", "skipped", when="setup"),
        # Fails in call and errors in teardown: counted once, as its worst outcome.
        _record(f"{gsheet}[dev-gsheet:row=4]", "failed"),
        _record(f"{gsheet}[dev-gsheet:row=4]", "failed", when="teardown"),
        _record(f"{gsheet}[ci-es-gsheet:row=4]", "skipped", wasxfail=True),
        _record("tests/nameres/test_nameres_api.py::test_openapi_json[dev]"),
        _record("tests/test_environment/test_env.py::test_google_sheet_has_test_cases"),
    ]
    lines = summarize_run(records, ["dev", "ci-es"], _sections(), {"Unit Tests"}, set())

    assert lines == [
        "Targets: dev, ci-es; included categories: Unit Tests; excluded categories: none",
        "NodeNorm [dev] https://nn.dev/: passed 1 of 3 run (33%) — 1 failed, 1 error; 1 skipped",
        "NodeNorm [ci-es] https://nn.ci-es/: passed 2 of 3 run (67%) — 1 xfailed; 1 skipped",
        "NameRes [dev] https://nr.dev/: passed 1 of 1 run (100%)",
        "test_environment: passed 1 of 1 run (100%)",
        "Outcomes differing across targets: 2",
        "  nodenorm/test_nodenorm_from_gsheet.py::test_normalization[gsheet:row=2]: dev=failed, ci-es=passed",
        "  nodenorm/test_nodenorm_from_gsheet.py::test_normalization[gsheet:row=4]: dev=error, ci-es=xfailed",
    ]


def test_summarize_run_single_target_has_no_comparison():
    records = [
        _record(
            "tests/nameres/test_nameres_api.py::test_openapi_json[dev]",
            "skipped",
            when="setup",
        )
    ]
    lines = summarize_run(records, ["dev"], _sections(), set(), {"Slow"})
    assert lines == [
        "Targets: dev; included categories: all; excluded categories: Slow",
        "NameRes [dev] https://nr.dev/: nothing run; 1 skipped",
    ]
