"""Unit tests for the end-of-run summary (build_summary/render_summary in tests/_pytest_helpers.py). No network."""

import configparser

import pytest

from tests._pytest_helpers import build_summary, plain_text, render_summary

pytestmark = pytest.mark.unit

GSHEET = "tests/nodenorm/test_nodenorm_from_gsheet.py::test_normalization"
RED = {"red": True}
GREEN = {"green": True}
DIM = {"light": True}


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


def _records():
    return [
        _record(f"{GSHEET}[dev-gsheet:row=1]", target="dev"),
        _record(f"{GSHEET}[ci-es-gsheet:row=1]", target="ci-es"),
        _record(f"{GSHEET}[dev-gsheet:row=2]", "failed", target="dev"),
        _record(f"{GSHEET}[ci-es-gsheet:row=2]", target="ci-es"),
        # Skipped by category filter: not counted towards the pass rate.
        _record(f"{GSHEET}[dev-gsheet:row=3]", "skipped", when="setup", target="dev"),
        _record(
            f"{GSHEET}[ci-es-gsheet:row=3]", "skipped", when="setup", target="ci-es"
        ),
        # Fails in call and errors in teardown: counted once, as its worst outcome.
        _record(f"{GSHEET}[dev-gsheet:row=4]", "failed", target="dev"),
        _record(f"{GSHEET}[dev-gsheet:row=4]", "failed", when="teardown", target="dev"),
        _record(
            f"{GSHEET}[ci-es-gsheet:row=4]", "skipped", wasxfail=True, target="ci-es"
        ),
        # A strict XPASS counts against the pass rate; an xfail (above) doesn't.
        _record(
            f"{GSHEET}[ci-es-gsheet:row=5]",
            "failed",
            target="ci-es",
            msg="[XPASS(strict)] known",
        ),
        # A test name carrying a control character is printed escaped.
        _record(f"{GSHEET}[dev-gsheet:row=\x1b[2J]", target="dev"),
        _record(f"{GSHEET}[ci-es-gsheet:row=\x1b[2J]", "failed", target="ci-es"),
        _record(
            "tests/nameres/test_nameres_api.py::test_openapi_json[dev]", target="dev"
        ),
        # A parameter that looks like a target doesn't make a test per-target: only the
        # "target" property does.
        _record("tests/unit/test_babel_release.py::test_name[2026sep24-dev]"),
        # A file directly in tests/ is its own group, named after the file; a slash in a
        # parameter doesn't make one.
        _record("tests/test_cache_dir.py::test_cache_dir[a/b]"),
        _record("tests/test_environment/test_env.py::test_google_sheet_has_test_cases"),
    ]


def _summary(records=None, targets=("dev", "ci-es"), include=("Unit Tests",)):
    records = _records() if records is None else records
    return build_summary(records, list(targets), _sections(), set(include), set())


def test_build_summary():
    summary = _summary()
    assert summary.counts[("nodenorm", "dev")] == {
        "passed": 2,
        "failed": 1,
        "error": 1,
        "xpassed": 0,
        "xfailed": 0,
        "skipped": 1,
    }
    assert summary.counts[("unit", "?")]["passed"] == 1
    assert ("unit", "dev") not in summary.counts
    assert summary.urls == {
        ("nodenorm", "dev"): "https://nn.dev/",
        ("nodenorm", "ci-es"): "https://nn.ci-es/",
        ("nameres", "dev"): "https://nr.dev/",
    }
    # Files count distinct tests, not one per target.
    assert summary.files["nodenorm"] == {"nodenorm/test_nodenorm_from_gsheet.py": 6}
    assert summary.files["test_cache_dir.py"] == {"test_cache_dir.py": 1}


def test_render_summary():
    lines = plain_text(render_summary(_summary()))
    assert lines == [
        "Targets: dev, ci-es",
        "Sheet categories: Unit Tests · excluded: none",
        "Result: NodeNorm ✗ dev, ci-es · NameRes ✓ · Other ✓",
        "",
        "                     rate  passed  failed  error  xpass  │  xfail  skip  URL",
        "NodeNorm",
        "  dev                 50%     2/4       1      1      ·  │      ·     1  https://nn.dev/",
        "  ci-es               50%     2/4       1      ·      1  │      1     1  https://nn.ci-es/",
        "NameRes",
        "  dev                100%     1/1       ·      ·      ·  │      ·     ·  https://nr.dev/",
        "Other",
        "  test_cache_dir.py  100%     1/1       ·      ·      ·  │      ·     ·",
        "  test_environment   100%     1/1       ·      ·      ·  │      ·     ·  (test_env.py: 1)",
        "  unit               100%     1/1       ·      ·      ·  │      ·     ·  (test_babel_release.py: 1)",
        "",
        "Outcomes differing across targets: 3",
        # Failures and errors first; then by size, then by pattern.
        "  error on dev; xfailed on ci-es (1)",
        "    'nodenorm/test_nodenorm_from_gsheet.py::test_normalization[gsheet:row=4]'",
        "  failed on dev; passed on ci-es (1)",
        "    'nodenorm/test_nodenorm_from_gsheet.py::test_normalization[gsheet:row=2]'",
        "  passed on dev; failed on ci-es (1)",
        "    'nodenorm/test_nodenorm_from_gsheet.py::test_normalization[gsheet:row=\\x1b[2J]'",
    ]


def test_render_summary_markup():
    # Cells are padded to their column; compare the text without the padding.
    lines = [
        [(text.strip(), markup) for text, markup in line]
        for line in render_summary(_summary())
    ]
    nodenorm_dev = lines[6]
    assert ("1", RED) in nodenorm_dev  # the failed count
    assert ("50%", RED) in nodenorm_dev
    assert ("·", DIM) in nodenorm_dev
    assert ("100%", GREEN) in lines[9]  # NameRes dev
    assert ("NodeNorm ✗ dev, ci-es", RED) in lines[2]
    assert ("NameRes ✓", GREEN) in lines[2]
    assert ("failed", RED) in lines[18] and ("passed", GREEN) in lines[18]


def test_rate_rounds_down():
    # 199 of 200 is 99.5%, which must not print as 100% while a test fails.
    records = [_record(f"{GSHEET}[dev-r{i}]", target="dev") for i in range(199)]
    records.append(_record(f"{GSHEET}[dev-r199]", "failed", target="dev"))
    lines = plain_text(render_summary(_summary(records, targets=["dev"])))
    assert lines[6].startswith("  dev   99%  199/200       1")


def test_single_target_has_no_comparison():
    records = [
        _record(
            "tests/nameres/test_nameres_api.py::test_openapi_json[dev]",
            "skipped",
            when="setup",
            target="dev",
        )
    ]
    summary = build_summary(records, ["dev"], _sections(), set(), {"Slow"})
    assert plain_text(render_summary(summary)) == [
        "Targets: dev",
        "Sheet categories: all · excluded: Slow",
        "Result: NameRes — nothing passed or failed",
        "",
        "       rate  passed  failed  error  xpass  │  xfail  skip  URL",
        "NameRes",
        "  dev     —     0/0       ·      ·      ·  │      ·     1  https://nr.dev/",
    ]


def test_other_group_with_targets_and_many_files():
    records = [
        _record(f"tests/github_issues/test_{i}.py::test_it[dev]", target="dev")
        for i in range(7)
    ]
    records.append(
        _record(
            "tests/github_issues/test_0.py::test_it[ci-es]", "failed", target="ci-es"
        )
    )
    # Untargeted tests that fail are named as such in the result line.
    records.append(_record("tests/unit/test_x.py::test_it", "failed"))
    lines = plain_text(render_summary(_summary(records)))
    assert lines[2] == "Result: Other ✗ ci-es, untargeted"
    assert lines[5:10] == [
        "Other",
        "  github_issues  (test_0.py: 1, test_1.py: 1, test_2.py: 1, test_3.py: 1, "
        "test_4.py: 1, … 2 more files)",
        "    dev    100%     7/7       ·      ·      ·  │      ·     ·",
        "    ci-es    0%     0/1       1      ·      ·  │      ·     ·",
        "  unit       0%     0/1       1      ·      ·  │      ·     ·  (test_x.py: 1)",
    ]


def _differing_records():
    """Three groups: 12 tests failing on ci-es, 3 xfailing on ci-es, 2 skipped on ci-es."""
    records = []
    for name, n, ci_es in [
        ("fail", 12, {"outcome": "failed"}),
        ("xfail", 3, {"outcome": "skipped", "wasxfail": True}),
        ("skip", 2, {"outcome": "skipped", "when": "setup"}),
    ]:
        for i in range(n):
            records.append(_record(f"{GSHEET}[dev-{name}{i:02}]", target="dev"))
            records.append(
                _record(f"{GSHEET}[ci-es-{name}{i:02}]", target="ci-es", **ci_es)
            )
    return records


@pytest.mark.parametrize(
    "max_differences, listed, more_lines",
    [
        # The default: at most ten per group.
        (50, [10, 3, 2], ["    … and 2 more"]),
        # A total cap spent on the first groups.
        (11, [10, 1, 0], ["    … and 2 more", "    … and 2 more"]),
        (0, [0, 0, 0], []),
        (-1, [12, 3, 2], []),
    ],
)
def test_differences_are_grouped_and_capped(max_differences, listed, more_lines):
    lines = plain_text(render_summary(_summary(_differing_records()), max_differences))
    diff = lines[lines.index("Outcomes differing across targets: 17") + 1 :]
    headings = [
        line for line in diff if line.startswith("  ") and not line.startswith("    ")
    ]
    assert headings[:3] == [
        "  passed on dev; failed on ci-es (12)",
        "  passed on dev; xfailed on ci-es (3)",
        "  passed on dev; skipped on ci-es (2)",
    ]
    tests = [line for line in diff if line.startswith("    '")]
    assert len(tests) == sum(listed)
    assert [line for line in diff if line.startswith("    …")] == more_lines
    hint = "  (--summary-max-differences -1 lists all 17)"
    assert (hint in diff) == (sum(listed) < 17)
