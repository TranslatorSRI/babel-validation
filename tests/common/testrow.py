from dataclasses import dataclass
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

class TestStatus(Enum):
    Passed = "pass"
    Failed = "fail"
    Skipped = "skip"

    # Mark as not a test despite starting with TestRow.
    __test__ = False

@dataclass
class TestResult:
    status: TestStatus
    message: str = ""
    github_issue_test: 'GitHubIssueTest' = None

    # Mark as not a test despite starting with TestRow.
    __test__ = False


