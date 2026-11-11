# We store Babel test cases in the Babel Validation Google Sheet.
#
# The sheet ID is deliberately not checked in: it is the capability that grants
# access to the sheet, so it lives in the BABEL_VALIDATION_SHEET_ID environment
# variable (via .env locally, a repository secret in GitHub Actions) and must
# never appear in the code, the Git history, or anything we publish.
#
# This library contains classes and methods for accessing those test cases.
import csv
import io
from collections import Counter

import pytest
from _pytest.mark import ParameterSet

from . import fetch_sheet_csv
from ...core.testrow import TestRow


class GoogleSheetTestCases:
    """
    A class wrapping a Google Sheet that contains test cases.
    """

    def __str__(self):
        # No sheet ID here: this string ends up in assertion messages and pytest
        # output, which the dashboard publishes.
        return f"Google Sheet Test Cases ({len(self.rows)} test cases)"

    def __init__(self, google_sheet_id=None, cache_ttl_seconds: int = 3600):
        """Create a Google Sheet test case.

        :param google_sheet_id: The Google Sheet identifier to download test cases from. Defaults to
            the BABEL_VALIDATION_SHEET_ID environment variable (loaded from .env if present).
        :param cache_ttl_seconds: How long a cached download stays valid. pytest deletes the cache at the
            start of every run (see tests/conftest.py), so this TTL mainly protects other consumers
            (e.g. csv-to-babeltests) from reading stale data forever.
        """

        # The ID is deliberately not kept on the instance: nothing reads it, and
        # this object's str() ends up in assertion messages the dashboard publishes.
        self.csv_content = fetch_sheet_csv(
            "BABEL_VALIDATION_SHEET_ID",
            "Tests",
            sheet_id=google_sheet_id,
            cache_ttl_seconds=cache_ttl_seconds,
        )

        self.rows = []
        with io.StringIO(self.csv_content) as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.rows.append(row)

    def test_rows(
        self,
        test_id_prefix: str,
        test_nodenorm: bool = False,
        test_nameres: bool = False,
    ) -> list[ParameterSet]:
        """
        self.rows is the raw list of rows we got back from the Google Sheets. This method transforms that into
        a list of TestRows.

        :param test_id_prefix: The prefix for the row ID.

        :return: A list of TestRows for the rows in this file.
        """

        def has_nonempty_value(d: dict):
            return not all(not s for s in d.values())

        trows = []
        for count, row in enumerate(self.rows):
            # Note that count is off by two: presumably one for the header row and one because we count from zero
            # but Google Sheets counts from one.
            row_count = count + 2
            row_id = f"{test_id_prefix}:row={row_count}"

            if has_nonempty_value(row):
                tr = TestRow.from_data_row(row)

                if test_nodenorm:
                    if tr.ExpectPassInNodeNorm:
                        trows.append(pytest.param(tr, id=row_id))
                    else:
                        trows.append(
                            pytest.param(
                                tr,
                                marks=pytest.mark.xfail(
                                    reason=f"Test row {row_count} is marked as not expected to pass NodeNorm in the "
                                    f"Google Sheet: {tr}",
                                    strict=True,
                                ),
                                id=row_id,
                            )
                        )

                if test_nameres:
                    if tr.ExpectPassInNameRes:
                        trows.append(pytest.param(tr, id=row_id))
                    else:
                        trows.append(
                            pytest.param(
                                tr,
                                marks=pytest.mark.xfail(
                                    reason=f"Test row {row_count} is marked as not expected to pass NameRes in the "
                                    f"Google Sheet: {tr}",
                                    strict=True,
                                ),
                                id=row_id,
                            )
                        )

        return trows

    def categories(self):
        """Return a dict of all the categories of tests available with their counts."""
        return Counter(map(lambda t: t.get("Category", ""), self.rows))
