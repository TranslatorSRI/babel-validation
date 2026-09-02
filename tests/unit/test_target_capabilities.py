"""targets.ini declares per-target capabilities, and tests skip on the strength of them.

A capability that reads False when it should read True does not fail — it *skips*, and the
run stays green while testing nothing. That is the failure mode worth pinning: the checked-in
file is asserted directly, and both skips are exercised against a synthetic target.
"""

import configparser

import pytest

from tests.conftest import read_targets
from tests.nameres.test_blocklist import test_check_blocklist_entry as check_blocklist_entry
from tests.nameres import test_nameres_from_gsheet as nameres_gsheet
from tests.nameres.test_nameres_from_gsheet import test_label as check_label
from src.babel_validation.core.testrow import TestRow

pytestmark = pytest.mark.unit

CHECKED_IN = read_targets("tests/targets.ini")


def _section(text):
    cp = configparser.ConfigParser()
    cp.read_string(text)
    return cp["t"]


def test_every_checked_in_target_declares_a_parseable_capability():
    """getboolean raises on anything that is not a boolean literal, so a `flase` typo is a
    failure here rather than a target that quietly stops testing its blocklist."""
    for name in CHECKED_IN.sections():
        assert isinstance(CHECKED_IN[name].getboolean("NameResHasBlocklist", True), bool)


def test_only_the_elasticsearch_namelookup_declares_no_blocklist():
    without = {
        name for name in CHECKED_IN.sections()
        if not CHECKED_IN[name].getboolean("NameResHasBlocklist", True)
    }
    assert without == {"ci-es"}, "every other deployment applies the Translator blocklist"


def test_a_target_that_says_nothing_keeps_its_blocklist_coverage():
    """The default has to be true: a new target added without the key must not silently
    lose the blocklist tests."""
    quiet = _section("[t]\nNameResURL = https://example.invalid/\n")
    assert quiet.getboolean("NameResHasBlocklist", True) is True


# NameResLimit and NameResXFailIfInTop come from [DEFAULT] in the real file, and
# test_label reads both before it reaches the skip, so the synthetic target needs them too.
NO_BLOCKLIST = (
    "[DEFAULT]\nNameResLimit = 20\nNameResXFailIfInTop = 5\n\n"
    "[t]\nNameResURL = https://example.invalid/\nNameResHasBlocklist = false\n"
)


def test_blocklist_entries_skip_when_the_target_declares_no_blocklist():
    with pytest.raises(pytest.skip.Exception, match="declares no blocklist"):
        check_blocklist_entry(_section(NO_BLOCKLIST), blocklist_entry=None,
                              categories_include=set())


def _negative_row(**overrides):
    row = {"Category": "Unit Tests", "Flags": "negative", "Query Label": "mongoloid",
           "Preferred ID": "HP:0000582", "Passes in NameRes": "y"}
    row.update(overrides)
    return TestRow.from_data_row(row)


def test_negative_sheet_rows_skip_when_the_target_declares_no_blocklist():
    """A `negative` row asserts a CURIE is absent, which is the blocklist's job."""
    with pytest.raises(pytest.skip.Exception, match="declares no blocklist"):
        check_label(_section(NO_BLOCKLIST), _negative_row(),
                    test_category=lambda category: True, record_property=lambda *args: None)


def test_ordinary_sheet_rows_are_unaffected_by_the_declaration():
    """Only `negative` rows skip. This row has no labels to query, so it fails at the end
    of test_label without reaching the network — which is the point: a regression in the
    skip condition shows up as this Failed rather than as a live request."""
    # BaseException, not Exception: pytest's outcome exceptions derive from it. Catching
    # Failed specifically would be worse than useless — a regressed skip would then
    # propagate and mark *this* test skipped, which reads as passing.
    with pytest.raises(BaseException) as excinfo:
        check_label(_section(NO_BLOCKLIST), _negative_row(Flags="", **{"Query Label": ""}),
                    test_category=lambda category: True, record_property=lambda *args: None)
    assert not isinstance(excinfo.value, pytest.skip.Exception), \
        "a row without the negative flag must not be skipped by the blocklist capability"


class FakeResponse:
    ok = True

    def __init__(self, results):
        self._results = results

    def json(self):
        return self._results


def test_the_rank_is_recorded_even_though_the_row_only_soft_xfails(monkeypatch):
    """The rank-2-6 branch calls pytest.xfail(), so the row never shows up as a failure.
    Recording the rank first is the only reason a cross-environment comparison can see a
    demotion from rank 1 at all."""
    monkeypatch.setattr(
        nameres_gsheet.requests, "get",
        lambda url, params=None, timeout=None: FakeResponse(
            [{"curie": "OTHER:1", "label": "something else"},
             {"curie": "HP:0000582", "label": "the expected one"}]))

    recorded = {}
    row = _negative_row(Flags="")  # not a negative row; an ordinary one that got demoted
    with pytest.raises(BaseException) as excinfo:
        check_label(_section(NO_BLOCKLIST), row, test_category=lambda category: True,
                    record_property=lambda key, value: recorded.__setitem__(key, value))

    assert isinstance(excinfo.value, pytest.xfail.Exception), excinfo.value
    assert recorded["expected_rank"] == 2
