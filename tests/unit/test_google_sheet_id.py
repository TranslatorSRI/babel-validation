"""The Google Sheet ID is a secret capability: it comes only from the
BABEL_VALIDATION_SHEET_ID environment variable, and a missing or implausible
value must fail loudly rather than fetch something unexpected."""

import pytest

from src.babel_validation.sources.google_sheets.google_sheet_test_cases import (
    GoogleSheetTestCases,
)

pytestmark = pytest.mark.unit


def test_missing_sheet_id_fails_loudly(monkeypatch):
    # Set-but-empty, not deleted: dotenv.load_dotenv() will not override a key
    # already in os.environ, so this defeats any ID in the developer's .env.
    monkeypatch.setenv("BABEL_VALIDATION_SHEET_ID", "")
    with pytest.raises(RuntimeError, match="BABEL_VALIDATION_SHEET_ID"):
        GoogleSheetTestCases()


@pytest.mark.parametrize(
    "bad_id",
    [
        "too-short",
        '"quoted-sheet-id-from-a-dotenv-mistake"',
        "has spaces in the sheet id somewhere",
        "path/traversal/attempt-0123456789abcdef",
    ],
)
def test_implausible_sheet_id_is_rejected(monkeypatch, bad_id):
    monkeypatch.setenv("BABEL_VALIDATION_SHEET_ID", bad_id)
    with pytest.raises(RuntimeError, match="does not look like"):
        GoogleSheetTestCases()
