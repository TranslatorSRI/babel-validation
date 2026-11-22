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
