# We store Babel test cases in Google Sheets at
# https://docs.google.com/spreadsheets/d/11zebx8Qs1Tc3ShQR9nh4HRW8QSoo8k65w_xIaftN0no/edit?usp=sharing
#
# This library contains classes and methods for accessing those test cases.
import csv
import io
from dataclasses import dataclass
from collections import Counter

import pytest
import requests
from _pytest.mark import ParameterSet


@dataclass(frozen=True)
class TestRow:
    """
    A TestRow models a single row from a GoogleSheet.
    """
    Category: str
    ExpectPassInNodeNorm: bool
    ExpectPassInNameRes: bool
    Flags: set[str]
    QueryLabel: str
    PreferredLabel: str
    AdditionalLabels: list[str]
    QueryID: str
    PreferredID: str
    AdditionalIDs: list[str]
    Conflations: set[str]
    BiolinkClasses: set[str]
    Prefixes: set[str]
    Source: str
    SourceURL: str
    Notes: str

    # Mark as not a test despite starting with TestRow.
    __test__ = False

    # A string representation of this test row.
    def __str__(self):
        return f"TestRow of category {self.Category} for preferred {self.PreferredID} ({self.PreferredLabel}) with " + \
            f"query {self.QueryID} ({self.QueryLabel}) from source {self.Source} ({self.SourceURL})"


    @staticmethod
    def from_data_row(row):
        return TestRow(
            Category=row.get('Category', ''),
            ExpectPassInNodeNorm=row.get('Passes in NodeNorm', '') == 'y',
            ExpectPassInNameRes=row.get('Passes in NameRes', '') == 'y',
            Flags=set(row.get('Flags', '').split('|')),
            QueryLabel=row.get('Query Label', ''),
            QueryID=row.get('Query ID', ''),
            PreferredID=row.get('Preferred ID', ''),
            AdditionalIDs=row.get('Additional IDs', '').split('|'),
            PreferredLabel=row.get('Preferred Label', ''),
            AdditionalLabels=row.get('Additional Labels', '').split('|'),
            Conflations=set(row.get('Conflations', '').split('|')),
            BiolinkClasses=set(row.get('Biolink Classes', '').split('|')),
            Prefixes=set(row.get('Prefixes', '').split('|')),
            Source=row.get('Source', ''),
            SourceURL=row.get('Source URL', ''),
            Notes=row.get('Notes', '')
        )


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
        csv_url = f"https://docs.google.com/spreadsheets/d/{google_sheet_id}/gviz/tq?tqx=out:csv&sheet=Tests"
        response = requests.get(csv_url)
        self.csv_content = response.text

        self.rows = []
        with io.StringIO(self.csv_content) as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.rows.append(row)

    def test_rows(self, test_nodenorm: bool = False, test_nameres: bool = False) -> list[ParameterSet]:
        """
        self.rows is the raw list of rows we got back from the Google Sheets. This method transforms that into
        a list of TestRows.

        :return: A list of TestRows for the rows in this file.
        """
        def has_nonempty_value(d: dict):
            return not all(not s for s in d.values())

        trows = []
        for count, row in enumerate(self.rows):
            # Note that count is off by two: presumably one for the header row and one because we count from zero
            # but Google Sheets counts from one.

            if has_nonempty_value(row):
                tr = TestRow.from_data_row(row)

                if test_nodenorm:
                    if tr.ExpectPassInNodeNorm:
                        trows.append(pytest.param(tr))
                    else:
                        trows.append(pytest.param(
                            tr,
                            marks=pytest.mark.xfail(
                                reason=f"Test row {count + 2} is marked as not expected to pass NodeNorm in the "
                                       f"Google Sheet: {tr}",
                                strict=True)
                        ))

                if test_nameres:
                    if tr.ExpectPassInNameRes:
                        trows.append(pytest.param(tr))
                    else:
                        trows.append(pytest.param(
                            tr,
                            marks=pytest.mark.xfail(
                                reason=f"Test row {count + 2} is marked as not expected to pass NameRes in the "
                                       f"Google Sheet: {tr}",
                                strict=True)
                        ))

        return trows

    def categories(self):
        """ Return a dict of all the categories of tests available with their counts. """
        return Counter(map(lambda t: t.get('Category', ''), self.rows))