"""Unit tests for the pure helpers inside the NameRes log-analysis marimo notebook.

The notebook (`log-analysis/nameres/analyze_nameres_logs.py`) is a marimo app, not
an importable module: its directory name contains a hyphen and its cells are
`@app.cell` functions rather than module-level defs. So we load it by path and
pull the helpers out with `Cell.run()`, which resolves a cell's ancestors for us.

Only cells with *no* data dependency are run here. `parser`, `span_helpers` and
`chain_helpers` exist as separate cells precisely so this is possible: the log
exports they operate on are large and deliberately not checked in, so any test
that had to run `log_path` or `loader` could not run in CI.
"""

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

NOTEBOOK = (
    Path(__file__).parents[2] / "log-analysis" / "nameres" / "analyze_nameres_logs.py"
)


def _load_notebook():
    spec = importlib.util.spec_from_file_location(
        "analyze_nameres_logs_under_test", NOTEBOOK
    )
    module = importlib.util.module_from_spec(spec)
    # marimo's dataclass machinery resolves annotations against sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def notebook():
    assert NOTEBOOK.is_file(), f"notebook not found at {NOTEBOOK}"
    return _load_notebook()


@pytest.fixture(scope="module")
def parser(notebook):
    _output, defs = notebook.parser.run()
    return defs


@pytest.fixture(scope="module")
def spans(notebook):
    _output, defs = notebook.span_helpers.run()
    return defs


@pytest.fixture(scope="module")
def chain_helpers(notebook):
    _output, defs = notebook.chain_helpers.run()
    return defs


def _record(log_line, timestamp="2026-09-01 19:03:34.522"):
    return {
        "@timestamp": timestamp,
        "@message": {
            "log": log_line,
            "kubernetes": {
                "pod_name": "name-lookup-web-server-dep-1",
                "container_image": "example.dkr.ecr.amazonaws.com/name-lookup:v1.5.2",
            },
        },
    }


LOOKUP_LINE = (
    'INFO:api.server:Lookup query to Solr for "autism" (autocomplete=True, '
    "highlighting=False, offset=0, limit=100, "
    "biolink_types=['DiseaseOrPhenotypicFeature'], only_prefixes=MONDO|HP, "
    "exclude_prefixes=None, only_taxa=None) took 30.20ms "
    "(with 27.75ms waiting for Solr)"
)


# --- parse_record -----------------------------------------------------------


def test_parse_record_reads_every_field(parser):
    entry = parser["parse_record"](_record(LOOKUP_LINE), source_file="export.json")

    assert entry.query == "autism"
    assert entry.query_length == 6
    assert entry.autocomplete is True
    assert entry.highlighting is False
    assert entry.offset == 0
    assert entry.limit == 100
    assert entry.biolink_types == ["DiseaseOrPhenotypicFeature"]
    # '|'-delimited filter fields become lists; the literal 'None' becomes [].
    assert entry.only_prefixes == ["MONDO", "HP"]
    assert entry.exclude_prefixes == []
    assert entry.only_taxa == []
    assert entry.took_ms == pytest.approx(30.20)
    assert entry.solr_wait_ms == pytest.approx(27.75)
    assert entry.slow_query is False
    assert entry.pod_name == "name-lookup-web-server-dep-1"
    assert entry.image_tag == "v1.5.2"
    assert entry.source_file == "export.json"
    assert entry.time == datetime(2026, 9, 1, 19, 3, 34, 522000)


def test_parse_record_detects_slow_query_warning(parser):
    line = LOOKUP_LINE.replace("INFO:api.server:", "WARNING:api.server:SLOW QUERY: ")
    assert parser["parse_record"](_record(line)).slow_query is True


def test_parse_record_ignores_non_lookup_lines(parser):
    assert parser["parse_record"](_record("INFO:api.server:Starting up")) is None


def test_parse_record_rejects_a_lookup_line_it_cannot_parse(parser):
    """A recognized-but-unparseable line must fail loudly.

    Returning None here would silently drop real traffic from every statistic,
    which looks identical to that traffic not existing.
    """
    truncated = 'INFO:api.server:Lookup query to Solr for "autism" (autocomplete=True'
    with pytest.raises(ValueError, match="Unparseable NameRes lookup line"):
        parser["parse_record"](_record(truncated))


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("MONDO|HP", ["MONDO", "HP"]),
        ("None", []),
        ("", []),
        ("  ", []),
        ("MONDO", ["MONDO"]),
        ("MONDO||HP", ["MONDO", "HP"]),
    ],
)
def test_parse_filter_list_normalizes_empty_filters(notebook, raw, expected):
    line = LOOKUP_LINE.replace("only_prefixes=MONDO|HP", f"only_prefixes={raw}")
    _output, defs = notebook.parser.run()
    assert defs["parse_record"](_record(line)).only_prefixes == expected


# --- log_file_span ----------------------------------------------------------


def test_log_file_span_returns_earliest_and_latest(spans):
    records = [
        {"@timestamp": "2026-08-10 00:00:00.000"},
        {"@timestamp": "2026-08-03 14:47:06.540"},
        {"@timestamp": "2026-09-01 19:03:34.522"},
    ]
    start, end = spans["log_file_span"](records)
    assert start == datetime(2026, 8, 3, 14, 47, 6, 540000)
    assert end == datetime(2026, 9, 1, 19, 3, 34, 522000)


def test_log_file_span_rejects_an_empty_export(spans):
    with pytest.raises(ValueError, match="no records"):
        spans["log_file_span"]([])


# --- assert_no_overlapping_spans --------------------------------------------


def _span(start, end):
    return (datetime.fromisoformat(start), datetime.fromisoformat(end))


def test_disjoint_spans_are_accepted(spans):
    spans["assert_no_overlapping_spans"](
        {
            "a.json": _span("2026-08-03", "2026-08-25"),
            "b.json": _span("2026-08-27", "2026-09-01"),
        }
    )


def test_a_single_export_never_overlaps_itself(spans):
    spans["assert_no_overlapping_spans"]({"a.json": _span("2026-08-03", "2026-09-01")})


def test_no_exports_is_not_an_error(spans):
    spans["assert_no_overlapping_spans"]({})


@pytest.mark.parametrize(
    "case, b_span",
    [
        ("partial", ("2026-08-20", "2026-09-01")),
        ("contained", ("2026-08-10", "2026-08-12")),
        ("identical", ("2026-08-03", "2026-08-25")),
        # Closed intervals: a shared endpoint can hold the same log line twice.
        ("touching", ("2026-08-25", "2026-09-01")),
    ],
)
def test_overlapping_spans_are_rejected(spans, case, b_span):
    with pytest.raises(ValueError) as excinfo:
        spans["assert_no_overlapping_spans"](
            {"a.json": _span("2026-08-03", "2026-08-25"), "b.json": _span(*b_span)}
        )
    message = str(excinfo.value)
    assert "double-count" in message
    # The error has to name both files, or the reader cannot act on it.
    assert "a.json" in message and "b.json" in message, case


def test_every_overlapping_pair_is_reported(spans):
    with pytest.raises(ValueError) as excinfo:
        spans["assert_no_overlapping_spans"](
            {
                "a.json": _span("2026-08-01", "2026-08-31"),
                "b.json": _span("2026-08-10", "2026-08-20"),
                "c.json": _span("2026-08-15", "2026-08-25"),
            }
        )
    assert str(excinfo.value).startswith("3 pair(s)")


# --- assign_chains ----------------------------------------------------------

SHAPE = {
    "limit": 100,
    "biolink_types": [],
    "only_prefixes": [],
    "exclude_prefixes": [],
    "only_taxa": [],
}


def _frame(rows):
    """Build a time-sorted lookup frame from (query, seconds-from-t0[, overrides])."""
    t0 = pd.Timestamp("2026-09-01 12:00:00")
    built = [
        {"query": q, "time": t0 + pd.Timedelta(seconds=offset), **SHAPE, **extra}
        for q, offset, *rest in rows
        for extra in [rest[0] if rest else {}]
    ]
    # An empty list would give a frame with no columns at all, so name them.
    columns = ["query", "time", *SHAPE]
    return pd.DataFrame(built, columns=columns).sort_values("time")


def test_a_typed_prefix_run_forms_one_chain(chain_helpers):
    frame = _frame([("diab", 0), ("diabe", 2), ("diabet", 4), ("diabetes type 2", 6)])
    ids = chain_helpers["assign_chains"](frame, pd.Timedelta(seconds=60))
    assert ids.nunique() == 1


def test_backspacing_stays_in_the_same_chain(chain_helpers):
    frame = _frame([("salisylic", 0), ("salisyli", 1), ("salisyl", 2), ("salis", 3)])
    ids = chain_helpers["assign_chains"](frame, pd.Timedelta(seconds=60))
    assert ids.nunique() == 1


def test_prefix_matching_ignores_case(chain_helpers):
    frame = _frame([("cox", 0), ("COX1", 1)])
    ids = chain_helpers["assign_chains"](frame, pd.Timedelta(seconds=60))
    assert ids.nunique() == 1


def test_unrelated_queries_start_new_chains(chain_helpers):
    frame = _frame([("diab", 0), ("aspirin", 2), ("metformin", 4)])
    ids = chain_helpers["assign_chains"](frame, pd.Timedelta(seconds=60))
    assert ids.nunique() == 3


def test_a_pause_longer_than_the_gap_splits_a_chain(chain_helpers):
    frame = _frame([("diab", 0), ("diabe", 120)])
    assert (
        chain_helpers["assign_chains"](frame, pd.Timedelta(seconds=60)).nunique() == 2
    )
    assert (
        chain_helpers["assign_chains"](frame, pd.Timedelta(seconds=300)).nunique() == 1
    )


def test_a_different_request_shape_never_joins_a_chain(chain_helpers):
    """Two clients typing the same term through different widgets are not one user."""
    frame = _frame([("diab", 0), ("diabe", 2, {"limit": 10})])
    ids = chain_helpers["assign_chains"](frame, pd.Timedelta(seconds=60))
    assert ids.nunique() == 2


def test_interleaved_shapes_do_not_break_each_others_chains(chain_helpers):
    """Chain state is tracked per request shape, not per most-recent row."""
    frame = _frame(
        [
            ("diab", 0),
            ("aspirin", 1, {"limit": 10}),
            ("diabe", 2),
            ("aspirin t", 3, {"limit": 10}),
        ]
    )
    ids = chain_helpers["assign_chains"](frame, pd.Timedelta(seconds=60))
    assert ids.nunique() == 2
    assert ids.iloc[0] == ids.iloc[2]
    assert ids.iloc[1] == ids.iloc[3]


def test_chain_ids_align_with_the_frames_index(chain_helpers):
    """The result is assigned straight onto `df`, so a misaligned index would
    scramble every chain silently."""
    frame = _frame([("diab", 0), ("diabe", 2)])
    frame.index = [17, 4]
    ids = chain_helpers["assign_chains"](frame, pd.Timedelta(seconds=60))
    assert list(ids.index) == [17, 4]


def test_assign_chains_on_an_empty_frame(chain_helpers):
    ids = chain_helpers["assign_chains"](_frame([]), pd.Timedelta(seconds=60))
    assert len(ids) == 0


def test_request_shape_is_hashable_and_distinguishes_filters(chain_helpers):
    base = pd.Series(SHAPE)
    filtered = pd.Series({**SHAPE, "biolink_types": ["Disease"]})
    shape = chain_helpers["request_shape"]
    assert shape(base) != shape(filtered)
    assert len({shape(base), shape(filtered)}) == 2
