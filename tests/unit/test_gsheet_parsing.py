"""Offline tests for turning Google Sheet rows into parametrized test cases.

Everything here is parsing: ``TestRow.from_data_row`` maps sheet columns onto
fields, and ``GoogleSheetTestCases.test_rows`` turns those into pytest
parameters. Both fail quietly rather than loudly -- a renamed column yields an
empty string, and a mis-numbered row yields a test ID that points a maintainer
at the wrong line of the sheet -- so the mapping and the numbering are pinned
here.

``requests.get`` is replaced with a canned CSV, so nothing here touches the
network.
"""

from types import SimpleNamespace

import pytest

from babel_validation.core.testrow import TestRow
from babel_validation.sources.google_sheets import google_sheet_test_cases as gsheet_module
from babel_validation.sources.google_sheets.google_sheet_test_cases import GoogleSheetTestCases
from tests._pytest_helpers import deselected_by_markexpr

pytestmark = pytest.mark.unit

COLUMNS = [
    "Category",
    "Passes in NodeNorm",
    "Passes in NameRes",
    "Flags",
    "Query Label",
    "Query ID",
    "Preferred ID",
    "Additional IDs",
    "Preferred Label",
    "Additional Labels",
    "Conflations",
    "Biolink Classes",
    "Prefixes",
    "Source",
    "Source URL",
    "Notes",
]

# Row 2 passes both services, row 3 passes neither, row 4 is blank, row 5 passes
# only NodeNorm. Sheet numbering starts at 2 because row 1 is the header.
SHEET_CSV = (
    ",".join(COLUMNS) + "\n"
    "Unit Tests,y,y,flagA|flagB,diabetes,MONDO:0005148,MONDO:0005148,DOID:9352,"
    "diabetes mellitus,DM|diabetes,GeneProtein,biolink:Disease,MONDO|DOID,"
    "Handmade,https://example.org/1,a note\n"
    "Unit Tests,n,n,,asthma,MONDO:0004979,MONDO:0004979,,asthma,,,biolink:Disease,MONDO,"
    "Handmade,https://example.org/2,\n"
    ",,,,,,,,,,,,,,,\n"
    "Slow,y,n,,aspirin,CHEBI:15365,CHEBI:15365,,aspirin,,,biolink:SmallMolecule,CHEBI,"
    "Handmade,https://example.org/3,\n"
)


@pytest.fixture
def gsheet(monkeypatch, tmp_path):
    """A GoogleSheetTestCases built from SHEET_CSV instead of a download."""

    class FakeResponse:
        text = SHEET_CSV

        def raise_for_status(self):
            pass

    monkeypatch.setattr(gsheet_module.requests, "get", lambda url, timeout: FakeResponse())
    # Keep the on-disk CSV cache out of the real temp directory, so a previous
    # run of this test cannot serve a stale sheet to this one.
    monkeypatch.setattr(gsheet_module.tempfile, "gettempdir", lambda: str(tmp_path))
    return GoogleSheetTestCases(google_sheet_id="unit-test-sheet")


# --- TestRow.from_data_row ------------------------------------------------


def test_from_data_row_maps_every_column():
    row = dict(zip(COLUMNS, SHEET_CSV.splitlines()[1].split(",")))

    tr = TestRow.from_data_row(row)

    # Pins the sheet's column headings: rename one upstream and the
    # corresponding field silently becomes empty rather than raising.
    assert tr.Category == "Unit Tests"
    assert tr.ExpectPassInNodeNorm is True
    assert tr.ExpectPassInNameRes is True
    assert tr.Flags == {"flagA", "flagB"}
    assert tr.QueryLabel == "diabetes"
    assert tr.QueryID == "MONDO:0005148"
    assert tr.PreferredID == "MONDO:0005148"
    assert tr.AdditionalIDs == ["DOID:9352"]
    assert tr.PreferredLabel == "diabetes mellitus"
    assert tr.AdditionalLabels == ["DM", "diabetes"]
    assert tr.Conflations == {"GeneProtein"}
    assert tr.BiolinkClasses == {"biolink:Disease"}
    assert tr.Prefixes == {"MONDO", "DOID"}
    assert tr.Source == "Handmade"
    assert tr.SourceURL == "https://example.org/1"
    assert tr.Notes == "a note"


@pytest.mark.parametrize(
    ("cell", "expected"),
    [("y", True), ("Y", True), (" y ", True), ("n", False), ("", False), ("yes", False)],
)
def test_expect_pass_accepts_only_a_trimmed_y(cell, expected):
    tr = TestRow.from_data_row({"Passes in NodeNorm": cell})
    assert tr.ExpectPassInNodeNorm is expected


def test_missing_columns_become_empty_rather_than_raising():
    # from_data_row uses .get() throughout, so a sheet missing a column still
    # parses. That is what makes the mapping test above worth having.
    tr = TestRow.from_data_row({})
    assert tr.Category == ""
    assert tr.ExpectPassInNodeNorm is False


def test_empty_multi_value_cells_yield_one_empty_entry():
    # "".split("|") == [""], so an empty cell is a one-element collection
    # holding "", not an empty one. Consumers have to treat "" as absent.
    tr = TestRow.from_data_row({"Flags": "", "Additional IDs": ""})
    assert tr.Flags == {""}
    assert tr.AdditionalIDs == [""]


# --- GoogleSheetTestCases -------------------------------------------------


def test_rows_are_numbered_as_in_the_sheet(gsheet):
    params = gsheet.test_rows("gsheet", test_nodenorm=True)

    # Rows 2 and 5 pass NodeNorm, row 3 does not (and is xfailed), row 4 is
    # blank and dropped -- but dropping it must not renumber row 5.
    assert [p.id for p in params] == ["gsheet:row=2", "gsheet:row=3", "gsheet:row=5"]


def test_blank_rows_are_dropped(gsheet):
    assert len(gsheet.rows) == 4, "the blank row survives CSV parsing"
    assert len(gsheet.test_rows("gsheet", test_nodenorm=True)) == 3, "but not parametrization"


def test_rows_not_expected_to_pass_are_marked_strict_xfail(gsheet):
    params = {p.id: p for p in gsheet.test_rows("gsheet", test_nodenorm=True)}

    assert params["gsheet:row=2"].marks == ()
    (mark,) = params["gsheet:row=3"].marks
    assert mark.name == "xfail"
    # strict=True so a row that starts passing fails the run and gets updated
    # in the sheet, instead of silently staying marked as broken.
    assert mark.kwargs["strict"] is True
    assert "row 3" in mark.kwargs["reason"]


def test_nodenorm_and_nameres_select_different_rows(gsheet):
    nodenorm_ids = [p.id for p in gsheet.test_rows("gsheet", test_nodenorm=True)]
    nameres_ids = [p.id for p in gsheet.test_rows("gsheet", test_nameres=True)]

    # Row 5 passes NodeNorm but not NameRes, so it is xfailed for one and not
    # the other -- both lists contain it, but with different marks.
    assert nodenorm_ids == nameres_ids == ["gsheet:row=2", "gsheet:row=3", "gsheet:row=5"]
    nameres_row5 = next(p for p in gsheet.test_rows("gsheet", test_nameres=True) if p.id == "gsheet:row=5")
    nodenorm_row5 = next(p for p in gsheet.test_rows("gsheet", test_nodenorm=True) if p.id == "gsheet:row=5")
    assert nameres_row5.marks != ()
    assert nodenorm_row5.marks == ()


def test_neither_flag_yields_nothing(gsheet):
    assert gsheet.test_rows("gsheet") == []


def test_categories_counts_rows_including_blanks(gsheet):
    assert gsheet.categories() == {"Unit Tests": 2, "Slow": 1, "": 1}


# --- deselected_by_markexpr -----------------------------------------------
#
# This helper is what keeps `pytest -m unit` -- the command CI runs -- from
# downloading the Google Sheet during collection. It lives here because the
# fetch it defers is the one the tests above stand in for. It is written to
# fail open, so every case below also checks it does not suppress a test that
# pytest would have run.


class FakeMetafunc:
    def __init__(self, markexpr, own_markers=()):
        self.config = self
        self.definition = self
        self._markexpr = markexpr
        self._own_markers = own_markers

    def getoption(self, name):
        assert name == "markexpr"
        return self._markexpr

    def iter_markers(self):
        # The helper only reads .name, and a real pytest.mark for an
        # unregistered marker would warn.
        return [SimpleNamespace(name=name) for name in self._own_markers]


@pytest.mark.parametrize(
    ("markexpr", "own_markers", "expected"),
    [
        ("", (), False),  # no -m filter: always keep, and never fetch needlessly
        ("unit", (), True),  # `-m unit` on an unmarked test: deselected, skip the fetch
        ("unit", ("unit",), False),  # `-m unit` on a unit test: keep
        ("not unit", (), False),  # `-m "not unit"` on an unmarked test: keep
        ("not unit", ("unit",), True),
        ("unit and not slow", ("unit", "slow"), True),
        ("(((", (), False),  # unparseable: let pytest report it, do not suppress
    ],
)
def test_deselected_by_markexpr(markexpr, own_markers, expected):
    assert deselected_by_markexpr(FakeMetafunc(markexpr, own_markers)) is expected
