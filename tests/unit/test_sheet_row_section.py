"""Unit tests for the "Google Sheet row" failure-report section (sheet_row_section in tests/_pytest_helpers.py). No network."""

import pytest

from tests._pytest_helpers import sheet_row_section

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
    assert sheet_row_section(props).splitlines() == [
        "Category:    'Unit Tests'",
        "Source:      'NodeNorm issue'",
        "Source URL:  'https://github.com/NCATSTranslator/Babel/issues/1'",
        "Query ID:    'MESH:D014867'",
        "Query label: ''",
    ]


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
    assert max(len(line) for line in section.splitlines()) < 250
