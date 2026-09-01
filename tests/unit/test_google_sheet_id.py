"""Google Sheet IDs are secret capabilities: they come only from environment
variables, and a missing or implausible value must fail loudly rather than
fetch something unexpected."""

import pytest

from src.babel_validation.sources.google_sheets import resolve_sheet_id
from src.babel_validation.sources.google_sheets.google_sheet_test_cases import (
    GoogleSheetTestCases,
)

pytestmark = pytest.mark.unit

ENV_VARS = ["BABEL_VALIDATION_SHEET_ID", "BABEL_VALIDATION_BLOCKLIST_SHEET_ID"]


@pytest.mark.parametrize("env_var", ENV_VARS)
def test_missing_sheet_id_fails_loudly(monkeypatch, env_var):
    # Set-but-empty, not deleted: dotenv.load_dotenv() will not override a key
    # already in os.environ, so this defeats any ID in the developer's .env.
    monkeypatch.setenv(env_var, "")
    with pytest.raises(RuntimeError, match=env_var):
        resolve_sheet_id(env_var)


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
        resolve_sheet_id("BABEL_VALIDATION_SHEET_ID")
    # An explicit argument gets the same format check.
    with pytest.raises(RuntimeError, match="does not look like"):
        resolve_sheet_id("BABEL_VALIDATION_SHEET_ID", bad_id)


def test_google_sheet_test_cases_uses_the_env_var(monkeypatch):
    monkeypatch.setenv("BABEL_VALIDATION_SHEET_ID", "")
    with pytest.raises(RuntimeError, match="BABEL_VALIDATION_SHEET_ID"):
        GoogleSheetTestCases()
