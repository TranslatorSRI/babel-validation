# Test whether the test environment is functional.
import json

from src.babel_validation.sources.google_sheets.google_sheet_test_cases import GoogleSheetTestCases


def test_google_sheet_has_test_cases():
    gsheet = GoogleSheetTestCases()
    assert gsheet.rows, f"Invalid value for Google Sheets: {gsheet.rows}"
    assert len(gsheet.rows) > 1000, f"Too few test cases in {gsheet}"

    # If something has gone wrong, writing out the first 10 lines can help figure out what's going wrong.
    print(f"Found {len(gsheet.rows)} test cases in {gsheet}: {json.dumps(gsheet.rows[:10], indent=2)}")

    categories = gsheet.categories()
    assert 'Unit Tests' in categories
