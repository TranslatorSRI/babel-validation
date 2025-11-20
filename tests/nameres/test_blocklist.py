import csv
import io
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import requests
import pytest


# The Translator Blocklist is stored in a private GitHub repository; however,
# we are currently using a spreadsheet to manage "Red Team" exercises where
# multiple Translator members try out different offensive terms and log them
# into a single spreadsheet. Eventually this test will support both, but since
# my immediate need is to check the spreadsheet, I'll start with that.
@dataclass(frozen=True)
class BlocklistEntry:
    """
    A single Blocklist entry.
    """
    Query: Optional[str] = None
    CURIE: Optional[str] = None
    Blocked: str = None
    Status: str = None
    Issue: str = None
    TreatsOnly: str = None
    Submitter: str = None
    Comment: str = None

    def is_blocked(self):
        """ Is this term supposed to be blocked? """
        if self.Blocked is not None and self.Blocked == 'y':
            return True
        return False

    @staticmethod
    def from_gsheet_dict(row):
        """
        Given a dictionary from a row in Google Sheets, fill in the necessary fields.

        :return: A BlocklistEntry with the filled in fields.
        """

        return BlocklistEntry(
            Query=row.get('String (optional)', None),
            CURIE=row.get('CURIE (optional)', None),
            Blocked=row['Blocked?'],
            Status=row['Status (Feb 21, 2024)'],
            Issue=row['Blocklist issue'],
            TreatsOnly=row['Block for "treats" only?'],
            Submitter=row['Submitter'],
            Comment=row['Comment (optional)'],
        )


def load_blocklist_from_gsheet():
    """
    Load the Blocklist from a Google Sheet.

    :param google_sheet_id: The Google Sheet ID containing the blocklist.
    :return: A list of BlocklistEntry.
    """
    google_sheet_id = '1UR2eplHBvFRwaSIVOhlB44wpfNPY1z7AVzUkqzDqIWA'
    csv_url = f"https://docs.google.com/spreadsheets/d/{google_sheet_id}/gviz/tq?tqx=out:csv&sheet=Tests"

    response = requests.get(csv_url)
    csv_content = response.text

    rows = []
    with io.StringIO(csv_content) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(BlocklistEntry.from_gsheet_dict(row))

    return rows

# Parameterize blocklist entries.
blocklist_entries = load_blocklist_from_gsheet()


@pytest.mark.parametrize("blocklist_entry", blocklist_entries)
def test_check_blocklist_entry(target_info, blocklist_entry, categories_include, categories_exclude):
    """
    Test whether a NameRes instance has blocked every item from a blocklist.

    :param target_info: The test target information.
    """
    nameres_url = target_info['NameResURL']
    nameres_url_reverse_lookup = nameres_url + 'reverse_lookup'

    # If there is any test category provided, this test is not relevant and we can skip it.
    if categories_include or categories_exclude:
        pytest.skip(f"Skipping blocklist entry as it is not part of any category and the category filter is set to include {categories_include} and exclude {categories_exclude}.")
        return

    # Only "blocked" entries are considered, since most of the spreadsheet is things we decided _not_ to block.
    if blocklist_entry.Blocked == 'y':
        flag_expect_present = False
    elif blocklist_entry.Blocked == 'n':
        flag_expect_present = True
    else:
        logging.info(f"Skipping blocklist entry as it is not asserted to be blocked: {blocklist_entry}")
        return

    if flag_expect_present and not blocklist_entry.CURIE:
        # We've got a bunch of these, just ignore them.
        pytest.skip(f"Blocklist entry expected to not be blocked, but no CURIE provided: {blocklist_entry}")

    assert blocklist_entry.CURIE, f"Blocklist entry claims to be blocked, but does not have a CURIE: {blocklist_entry}"

    # Someday we would like to do this with the query as well, but that would require some work.
    # So we only test the CURIE for now.
    response = requests.get(nameres_url_reverse_lookup, params={
        'curies': blocklist_entry.CURIE,
    })
    assert response.ok
    result = response.json()[blocklist_entry.CURIE]

    if flag_expect_present:
        assert result != {}, f"Expected {blocklist_entry.CURIE} to be present on {nameres_url_reverse_lookup}, but found: {result}"
    else:
        assert result == {}, f"Expected {blocklist_entry.CURIE} to be absent on {nameres_url_reverse_lookup}, but found: {result}"
