from dataclasses import dataclass, field
from enum import Enum


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
    # Lists in sheet order, not sets: a set's per-process iteration order made test_label's outcome
    # (it stops at the first class that misses) and its request's prefix order depend on the hash
    # seed (#193).
    BiolinkClasses: list[str]
    # Empty entries dropped, so an empty cell is [] and test_label sends no prefix filter.
    Prefixes: list[str]
    Source: str
    # Free text in the sheet, so it could link anywhere, including to another Google Sheet, whose
    # ID is its capability. Left out of repr() and str(): pytest prints a failing test's arguments
    # (`test_row = TestRow(...)`) and its message into public Actions logs. A test that needs it
    # passes it through validate_source_url() first (#197).
    SourceURL: str = field(repr=False)
    Notes: str

    # Mark as not a test despite starting with Test*.
    __test__ = False

    # A string representation of this test row, for failure messages. Every cell is !r-escaped,
    # since the sheet is untrusted and the message reaches terminals; see SourceURL for why it is
    # not here.
    def __str__(self):
        return f"TestRow of category {self.Category!r} for preferred {self.PreferredID!r} ({self.PreferredLabel!r}) " + \
            f"with query {self.QueryID!r} ({self.QueryLabel!r}) from source {self.Source!r}"


    @staticmethod
    def from_data_row(row):
        return TestRow(
            Category=row.get('Category', ''),
            ExpectPassInNodeNorm=row.get('Passes in NodeNorm', '').strip().lower() == 'y',
            ExpectPassInNameRes=row.get('Passes in NameRes', '').strip().lower() == 'y',
            Flags=set(row.get('Flags', '').split('|')),
            QueryLabel=row.get('Query Label', ''),
            QueryID=row.get('Query ID', ''),
            PreferredID=row.get('Preferred ID', ''),
            AdditionalIDs=row.get('Additional IDs', '').split('|'),
            PreferredLabel=row.get('Preferred Label', ''),
            AdditionalLabels=row.get('Additional Labels', '').split('|'),
            Conflations=set(row.get('Conflations', '').split('|')),
            BiolinkClasses=row.get('Biolink Classes', '').split('|'),
            Prefixes=[p for p in row.get('Prefixes', '').split('|') if p],
            Source=row.get('Source', ''),
            SourceURL=row.get('Source URL', ''),
            Notes=row.get('Notes', '')
        )

class TestStatus(Enum):
    Passed = "pass"
    Failed = "fail"
    Skipped = "skip"

    # Mark as not a test despite starting with Test*.
    __test__ = False

@dataclass
class TestResult:
    status: TestStatus
    message: str = ""

    # Mark as not a test despite starting with Test*.
    __test__ = False

