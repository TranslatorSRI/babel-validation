"""Unit tests for the "Google Sheet row" failure-report section (sheet_row_section in tests/_pytest_helpers.py). No network."""

import types

import pytest

from tests._pytest_helpers import sheet_row_section
from tests.conftest import _repositories_allowlist

pytestmark = pytest.mark.unit


def test_sheet_row_section():
    # As a sheet test records them with record_property, after conftest's "target".
    props = [
        ("target", "dev"),
        ("category", "Unit Tests"),
        ("source", "NodeNorm issue"),
        ("source_url", "https://github.com/NCATSTranslator/Babel/issues/1"),
        ("query_id", "MESH:D014867"),
        ("query_label", None),
    ]
    assert sheet_row_section(props, ["ncatstranslator/babel"]).splitlines() == [
        "Category:    'Unit Tests'",
        "Source:      'NodeNorm issue'",
        "Source URL:  'https://github.com/NCATSTranslator/Babel/issues/1'",
        "Query ID:    'MESH:D014867'",
        "Query label: ''",
    ]


@pytest.mark.parametrize(
    "url",
    [
        "https://docs.google.com/spreadsheets/d/SOME_OTHER_SHEET/edit",
        "https://github.com/someone-else/repo/issues/1",
        "http://github.com/NCATSTranslator/Babel/issues/1",
    ],
)
def test_sheet_row_section_hides_source_urls_off_the_allowlist(url):
    # The section reaches public Actions logs, and the Source URL is free text in the sheet.
    section = sheet_row_section(
        [("category", "Unit Tests"), ("source_url", url)], ["ncatstranslator/babel"]
    )
    assert url not in section
    assert "Source URL:  (none that links" in section


def test_sheet_row_section_hides_every_source_url_without_an_allowlist():
    url = "https://github.com/NCATSTranslator/Babel/issues/1"
    assert url not in sheet_row_section(
        [("category", "Unit Tests"), ("source_url", url)]
    )


def test_sheet_row_section_only_for_sheet_tests():
    assert sheet_row_section([("target", "dev")]) is None
    assert sheet_row_section([]) is None


def test_sheet_row_section_escapes_and_truncates_cells():
    # Sheet cells are untrusted and the section reaches terminals and public logs.
    section = sheet_row_section(
        [("category", "\x1b[2J‮evil"), ("source", "x" * 10_000)]
    )
    assert "\x1b" not in section and "‮" not in section
    assert "'\\x1b[2J\\u202eevil'" in section
    assert max(len(line) for line in section.splitlines()) <= 213


@pytest.mark.parametrize("char", ["x", "‮", "\U000e0001"])
def test_sheet_row_section_bounds_lines_after_escaping(char):
    # repr() turns one non-printable character into up to ten, so truncating only before it
    # let a 200-character cell become a 2000-character line.
    section = sheet_row_section([("category", char * 10_000)])
    # A 12-character label column, a space, and at most 200 characters of cell.
    assert max(len(line) for line in section.splitlines()) <= 213


INNER_TESTS = """
import pytest

def test_fails(record_property):
    record_property("category", "Unit Tests")
    assert False

def test_passes(record_property):
    record_property("category", "Unit Tests")

def test_fails_without_a_row():
    assert False

@pytest.mark.xfail(strict=True)
def test_known_failure(record_property):
    record_property("category", "Unit Tests")
    assert False

@pytest.mark.xfail(strict=True)
def test_strict_xpass(record_property):
    record_property("category", "Unit Tests")
"""


def test_makereport_adds_the_section_only_to_real_failures(tmp_path, monkeypatch):
    # Runs the real wrapper from tests/conftest.py in a nested pytest run. Whether an xfail row
    # gets the section depends on that wrapper running outside pytest's skipping plugin, which
    # turns an expected failure into a skip and a strict XPASS into a failure. It is outermost
    # because a conftest registers after pytest's own plugins (`tryfirst` would keep it there);
    # `trylast`, or a change in how pluggy orders wrappers, would put it inside the skipping
    # plugin, and a strict XPASS would then lose its section.
    (tmp_path / "conftest.py").write_text(
        "from tests.conftest import pytest_runtest_makereport\n"
    )
    (tmp_path / "test_inner.py").write_text(INNER_TESTS)
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

    reports = {}

    class Recorder:
        @staticmethod
        def pytest_runtest_logreport(report):
            if report.when == "call":
                name = report.nodeid.split("::")[-1]
                reports[name] = (report.outcome, dict(report.sections))

    pytest.main(
        [str(tmp_path), "-q", "-p", "no:cacheprovider", "--import-mode=importlib"],
        plugins=[Recorder()],
    )

    assert reports["test_fails"][0] == "failed"
    assert "Category:    'Unit Tests'" in reports["test_fails"][1]["Google Sheet row"]
    assert reports["test_strict_xpass"][0] == "failed"
    assert "Google Sheet row" in reports["test_strict_xpass"][1]
    assert reports["test_known_failure"][0] == "skipped"
    for name in ("test_known_failure", "test_passes", "test_fails_without_a_row"):
        assert "Google Sheet row" not in reports[name][1], name


def _config(rootpath):
    return types.SimpleNamespace(rootpath=rootpath, stash=pytest.Stash())


def test_repositories_allowlist_reads_targets_ini_once(tmp_path):
    (tmp_path / "targets.ini").write_text(
        "[DEFAULT]\nRepositories =\n    NCATSTranslator/Babel\n    Org/Repo\n"
    )
    config = _config(tmp_path)
    assert _repositories_allowlist(config) == ["ncatstranslator/babel", "org/repo"]
    # Read once per process: the sheet tests ask for it on every row.
    (tmp_path / "targets.ini").unlink()
    assert _repositories_allowlist(config) == ["ncatstranslator/babel", "org/repo"]


def test_repositories_allowlist_is_empty_without_targets_ini(tmp_path):
    # Empty hides every Source URL, rather than raising while a failure is being reported.
    assert _repositories_allowlist(_config(tmp_path)) == []
