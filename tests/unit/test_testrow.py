"""TestRow parses the Google Sheet's pipe-separated filter columns.

A blank cell must parse to an empty set, not `{''}`: test_nameres_from_gsheet
only sends `only_prefixes` / `only_taxa` when the field is truthy.
"""

import pytest

from src.babel_validation.core.testrow import TestRow

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("cell, expected", [
    ("", set()),
    ("NCBITaxon:9606", {"NCBITaxon:9606"}),
    ("NCBITaxon:9606|NCBITaxon:10090|NCBITaxon:10116|NCBITaxon:7955",
     {"NCBITaxon:9606", "NCBITaxon:10090", "NCBITaxon:10116", "NCBITaxon:7955"}),
    (" NCBITaxon:9606 | |NCBITaxon:10090|", {"NCBITaxon:9606", "NCBITaxon:10090"}),
])
def test_only_taxa(cell, expected):
    assert TestRow.from_data_row({"Only Taxa": cell}).OnlyTaxa == expected


def test_missing_columns_parse_empty():
    row = TestRow.from_data_row({})
    assert row.OnlyTaxa == set()
    assert row.Prefixes == set()
    assert row.BiolinkClasses == set()


def test_prefixes():
    assert TestRow.from_data_row({"Prefixes": "MONDO|^HP"}).Prefixes == {"MONDO", "^HP"}


def test_biolink_classes():
    row = TestRow.from_data_row({"Biolink Classes": "biolink:Disease|!biolink:Gene"})
    assert row.BiolinkClasses == {"biolink:Disease", "!biolink:Gene"}
