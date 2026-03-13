import csv
import io
from dataclasses import dataclass
from typing import Optional

import requests


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
