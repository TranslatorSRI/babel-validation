from dataclasses import dataclass
from enum import Enum


def split_pipes(value: str) -> set[str]:
    """Split a pipe-separated cell into its non-empty entries.

    A bare `set(value.split('|'))` turns a blank cell into `{''}`, which is
    truthy, so a filter column like Prefixes or Only Taxa would look filled in
    on every row and send an empty filter to NameRes.
    """
    return {v.strip() for v in value.split('|') if v.strip()}


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
    OnlyTaxa: set[str]
    Source: str
    SourceURL: str
    Notes: str

    # Mark as not a test despite starting with Test*.
    __test__ = False

    # A string representation of this test row.
    def __str__(self):
        return f"TestRow of category {self.Category} for preferred {self.PreferredID} ({self.PreferredLabel}) with " + \
            f"query {self.QueryID} ({self.QueryLabel}) from source {self.Source} ({self.SourceURL})"


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
            # Not split_pipes(): test_nameres_from_gsheet loops over these, and a blank cell's ''
            # is what makes it run the lookup with no biolink_type.
            BiolinkClasses=set(row.get('Biolink Classes', '').split('|')),
            Prefixes=split_pipes(row.get('Prefixes', '')),
            OnlyTaxa=split_pipes(row.get('Only Taxa', '')),
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

