# We store Babel test cases in Google Sheets at
# https://docs.google.com/spreadsheets/d/11zebx8Qs1Tc3ShQR9nh4HRW8QSoo8k65w_xIaftN0no/edit?usp=sharing
#
# This library contains classes and methods for accessing those test cases.
import csv
import io
from collections import Counter

import requests


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

    def categories(self):
        """ Return a dict of all the categories of tests available with their counts. """
        return Counter(map(lambda t: t.get('Category', ''), self.rows))