
import pytest
from common.google_sheet_test_cases import GoogleSheetTestCases, TestRow

# We generate a set of tests from the GoogleSheetTestCases.
gsheet = GoogleSheetTestCases()


@pytest.mark.parametrize("test_row", gsheet.test_rows)
def test_query_label(test_row):
    labels_to_test = [test_row.QueryLabel].extend(test_row.AdditionalLabels)
    assert labels_to_test, f"No labels to test for {test_row}"