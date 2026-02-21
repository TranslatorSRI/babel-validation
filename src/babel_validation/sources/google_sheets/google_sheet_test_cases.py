# We store Babel test cases in Google Sheets at
# https://docs.google.com/spreadsheets/d/11zebx8Qs1Tc3ShQR9nh4HRW8QSoo8k65w_xIaftN0no/edit?usp=sharing
#
# This library contains classes and methods for accessing those test cases.
import csv
import hashlib
import io
import tempfile
import time
from collections import Counter
from pathlib import Path

import pytest
import requests
from _pytest.mark import ParameterSet
from filelock import FileLock

from src.babel_validation.core.testrow import TestRow

_CACHE_TTL = 3600  # 1 hour


class GoogleSheetTestCases:
    """
    A class wrapping a Google Sheet that contains test cases.
    """

    def __str__(self):
        return f"Google Sheet Test Cases ({len(self.rows)} test cases from {self.google_sheet_id})"

    def __init__(self, google_sheet_id="11zebx8Qs1Tc3ShQR9nh4HRW8QSoo8k65w_xIaftN0no"):
        """ Create a Google Sheet test case.

        :param google_sheet_id The Google Sheet identifier to download test cases from.
        """

        self.google_sheet_id = google_sheet_id

        sheet_hash = hashlib.md5(google_sheet_id.encode()).hexdigest()[:8]
        cache_file = Path(tempfile.gettempdir()) / f"babel_validation_gsheet_{sheet_hash}.csv"
        lock_file = cache_file.with_suffix(".lock")

        with FileLock(lock_file):
            if cache_file.exists() and (time.time() - cache_file.stat().st_mtime) < _CACHE_TTL:
                self.csv_content = cache_file.read_text(encoding="utf-8")
            else:
                csv_url = f"https://docs.google.com/spreadsheets/d/{google_sheet_id}/gviz/tq?tqx=out:csv&sheet=Tests"
                response = requests.get(csv_url)
                self.csv_content = response.text
                cache_file.write_text(self.csv_content, encoding="utf-8")

        self.rows = []
        with io.StringIO(self.csv_content) as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.rows.append(row)

    def test_rows(self, test_id_prefix: str, test_nodenorm: bool = False, test_nameres: bool = False) -> list[ParameterSet]:
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
            row_id = f"{test_id_prefix}:row={count + 2}"

            if has_nonempty_value(row):
                tr = TestRow.from_data_row(row)

                if test_nodenorm:
                    if tr.ExpectPassInNodeNorm:
                        trows.append(pytest.param(tr, id=row_id))
                    else:
                        trows.append(pytest.param(
                            tr,
                            marks=pytest.mark.xfail(
                                reason=f"Test row {count + 2} is marked as not expected to pass NodeNorm in the "
                                       f"Google Sheet: {tr}",
                                strict=True),
                            id=row_id
                        ))

                if test_nameres:
                    if tr.ExpectPassInNameRes:
                        trows.append(pytest.param(tr, id=row_id))
                    else:
                        trows.append(pytest.param(
                            tr,
                            marks=pytest.mark.xfail(
                                reason=f"Test row {count + 2} is marked as not expected to pass NameRes in the "
                                       f"Google Sheet: {tr}",
                                strict=True),
                            id=row_id
                        ))

        return trows

    def categories(self):
        """ Return a dict of all the categories of tests available with their counts. """
        return Counter(map(lambda t: t.get('Category', ''), self.rows))
