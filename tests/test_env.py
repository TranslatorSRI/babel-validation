# Test whether the test environment is functional.

from common.google_sheet_test_cases import GoogleSheetTestCases

def test_google_sheet_has_test_cases():
    gsheet = GoogleSheetTestCases()
    assert gsheet.rows, f"Invalid value for Google Sheets: {gsheet.rows}"
    assert len(gsheet.rows) > 1000, f"Too few test cases in {gsheet}"

    categories = gsheet.categories()
    assert 'Test' in categories