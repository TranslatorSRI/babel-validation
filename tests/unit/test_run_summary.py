"""Unit tests for the end-of-run summary (summarize_run in tests/_pytest_helpers.py). No network."""

import configparser

import pytest

from tests._pytest_helpers import summarize_run

pytestmark = pytest.mark.unit


def _record(
    nodeid, outcome="passed", when="call", wasxfail=False, target=None, msg=None
):
    # conftest's pytest_itemcollected records the target of every test that takes one.
    return {
        "id": nodeid,
        "when": when,
        "outcome": outcome,
        "wasxfail": wasxfail,
        "props": {"target": target} if target else {},
        "msg": msg,
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
        _record(f"{gsheet}[dev-gsheet:row=1]", target="dev"),
        _record(f"{gsheet}[ci-es-gsheet:row=1]", target="ci-es"),
        _record(f"{gsheet}[dev-gsheet:row=2]", "failed", target="dev"),
        _record(f"{gsheet}[ci-es-gsheet:row=2]", target="ci-es"),
        # Skipped by category filter: not counted towards the pass rate.
        _record(f"{gsheet}[dev-gsheet:row=3]", "skipped", when="setup", target="dev"),
        _record(
            f"{gsheet}[ci-es-gsheet:row=3]", "skipped", when="setup", target="ci-es"
        ),
        # Fails in call and errors in teardown: counted once, as its worst outcome.
        _record(f"{gsheet}[dev-gsheet:row=4]", "failed", target="dev"),
        _record(f"{gsheet}[dev-gsheet:row=4]", "failed", when="teardown", target="dev"),
        _record(
            f"{gsheet}[ci-es-gsheet:row=4]", "skipped", wasxfail=True, target="ci-es"
        ),
        # A strict XPASS counts against the pass rate; an xfail (above) doesn't.
        _record(
            f"{gsheet}[ci-es-gsheet:row=5]",
            "failed",
            target="ci-es",
            msg="[XPASS(strict)] known",
        ),
        # A test name carrying a control character is printed escaped.
        _record(f"{gsheet}[dev-gsheet:row=\x1b[2J]", target="dev"),
        _record(f"{gsheet}[ci-es-gsheet:row=\x1b[2J]", "failed", target="ci-es"),
        _record(
            "tests/nameres/test_nameres_api.py::test_openapi_json[dev]", target="dev"
        ),
        # A parameter that looks like a target doesn't make a test per-target: only the
        # "target" property does.
        _record("tests/unit/test_babel_release.py::test_name[2026sep24-dev]"),
        # A file directly in tests/ is its own component, named after the file; a slash in a
        # parameter doesn't make one.
        _record("tests/test_cache_dir.py::test_cache_dir[a/b]"),
        _record("tests/test_environment/test_env.py::test_google_sheet_has_test_cases"),
    ]
    lines = summarize_run(records, ["dev", "ci-es"], _sections(), {"Unit Tests"}, set())

    assert lines == [
        "Targets: dev, ci-es; included categories: Unit Tests; excluded categories: none",
        "NodeNorm [dev] https://nn.dev/: passed 2 of 4 (50%) — 1 failed, 1 error; not counted: 1 skipped",
        "NodeNorm [ci-es] https://nn.ci-es/: passed 2 of 4 (50%) — 1 failed, 1 xpassed; "
        "not counted: 1 xfailed, 1 skipped",
        "NameRes [dev] https://nr.dev/: passed 1 of 1 (100%)",
        "test_cache_dir.py: passed 1 of 1 (100%)",
        "test_environment: passed 1 of 1 (100%)",
        "unit: passed 1 of 1 (100%)",
        "Outcomes differing across targets: 3",
        # Sorted by key, and ESC sorts before the digits.
        "  'nodenorm/test_nodenorm_from_gsheet.py::test_normalization[gsheet:row=\\x1b[2J]': dev=passed, ci-es=failed",
        "  'nodenorm/test_nodenorm_from_gsheet.py::test_normalization[gsheet:row=2]': dev=failed, ci-es=passed",
        "  'nodenorm/test_nodenorm_from_gsheet.py::test_normalization[gsheet:row=4]': dev=error, ci-es=xfailed",
    ]


def test_summarize_run_single_target_has_no_comparison():
    records = [
        _record(
            "tests/nameres/test_nameres_api.py::test_openapi_json[dev]",
            "skipped",
            when="setup",
            target="dev",
        )
    ]
    lines = summarize_run(records, ["dev"], _sections(), set(), {"Slow"})
    assert lines == [
        "Targets: dev; included categories: all; excluded categories: Slow",
        "NameRes [dev] https://nr.dev/: nothing passed or failed; not counted: 1 skipped",
    ]
