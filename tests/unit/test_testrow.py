"""Unit tests for reading a Google Sheet row into a TestRow (src/babel_validation/core/testrow.py). No network."""

import os

import pytest

from src.babel_validation.core.testrow import TestRow, current_source_url
from src.babel_validation.tools.generate_report import read_targets, validate_source_url

pytestmark = pytest.mark.unit

TARGETS_INI = os.path.join(os.path.dirname(__file__), "..", "targets.ini")


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://github.com/TranslatorSRI/NodeNormalization/issues/85",
            "https://github.com/NCATSTranslator/NodeNormalization/issues/85",
        ),
        (
            "https://github.com/translatorsri/nameresolution/issues/26#issuecomment-1809231866",
            "https://github.com/NCATSTranslator/NameResolution/issues/26#issuecomment-1809231866",
        ),
        (
            "https://github.com/TranslatorSRI/Babel/issues/308",
            "https://github.com/NCATSTranslator/Babel/issues/308",
        ),
        (
            "https://github.com/TranslatorSRI/Babel",
            "https://github.com/NCATSTranslator/Babel",
        ),
    ],
)
def test_old_repo_names_are_rewritten(url, expected):
    assert current_source_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://github.com/NCATSTranslator/Babel/issues/525",
        "https://github.com/TranslatorSRI/babel-validation/issues/1",
        "https://github.com/TranslatorSRI/NodeNormalizationX/issues/1",
        "https://github.com/TranslatorSRI/NodeNormalization.evil/issues/1",
        "https://github.com/TranslatorSRI",
        "http://github.com/TranslatorSRI/Babel/issues/1",
        "https://github.com.evil.example/TranslatorSRI/Babel/issues/1",
        "https://example.org/TranslatorSRI/Babel/issues/1",
        "see https://github.com/TranslatorSRI/Babel/issues/1",
    ],
)
def test_other_urls_are_unchanged(url):
    assert current_source_url(url) == url


def test_sheet_row_source_url_passes_the_allowlist():
    # The point of the rewrite: a row citing an old repo name now gets a link in the
    # dashboard and the end-of-run summary.
    allowlist = read_targets(TARGETS_INI)[1]
    old = "https://github.com/TranslatorSRI/NodeNormalization/issues/85"
    assert validate_source_url(old, allowlist) is None

    row = TestRow.from_data_row({"Source URL": old})
    assert row.SourceURL == (
        "https://github.com/NCATSTranslator/NodeNormalization/issues/85"
    )
    assert validate_source_url(row.SourceURL, allowlist) == row.SourceURL


def test_biolink_classes_keep_sheet_order_and_repeats():
    # test_label stops at the first class that misses, so a set here made its outcome depend on
    # the hash seed (#193). Enough entries that a set would almost never keep this order.
    classes = [f"biolink:Class{i}" for i in range(20, 0, -1)] + ["biolink:Class5"]
    row = TestRow.from_data_row({"Biolink Classes": "|".join(classes)})
    assert row.BiolinkClasses == classes


def test_empty_biolink_classes_cell_is_one_empty_entry():
    # An empty cell is what makes test_label query without a Biolink class.
    assert TestRow.from_data_row({}).BiolinkClasses == [""]


def test_prefixes_keep_sheet_order():
    # test_label joins these into only_prefixes/exclude_prefixes, so a set reordered the request
    # from one process to the next (#193).
    prefixes = [f"PREFIX{i}" for i in range(20, 0, -1)] + ["^UMLS"]
    assert TestRow.from_data_row({"Prefixes": "|".join(prefixes)}).Prefixes == prefixes


@pytest.mark.parametrize("cell,expected", [("", []), ("CHEBI|", ["CHEBI"]), ("|^UMLS", ["^UMLS"])])
def test_prefixes_drop_empty_entries(cell, expected):
    # An empty entry used to make test_label send only_prefixes='' for every row.
    assert TestRow.from_data_row({"Prefixes": cell}).Prefixes == expected
