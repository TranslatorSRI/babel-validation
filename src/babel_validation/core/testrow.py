from dataclasses import dataclass
from enum import Enum


# Repositories that most Source URLs in the Google Sheet still cite under their old TranslatorSRI
# names. Only links into the targets.ini Repositories list are published (generate_report.py's
# validate_source_url()), and that list has the NCATSTranslator names, so without this rewrite
# about 1,300 of the sheet's 2,076 rows got no link. GitHub redirects both the rename and later
# issue transfers (most NodeNormalization issues the sheet cites are now in Babel), so the
# rewritten link still lands on the right issue. This is deliberately not an alias in the
# allowlist: Repositories also decides which repos the GitHub issue tests scan, and the rewrite
# goes away with the sheet (#184).
RENAMED_SOURCE_REPOS = {
    'translatorsri/babel': 'NCATSTranslator/Babel',
    'translatorsri/nodenormalization': 'NCATSTranslator/NodeNormalization',
    'translatorsri/nameresolution': 'NCATSTranslator/NameResolution',
}


def current_source_url(url):
    """
    Return a sheet Source URL with an old TranslatorSRI repository name replaced by its
    NCATSTranslator one (RENAMED_SOURCE_REPOS); any other URL is returned unchanged.
    """
    prefix = 'https://github.com/'
    if not url.startswith(prefix):
        return url
    org, _, rest = url[len(prefix):].partition('/')
    repo, sep, path = rest.partition('/')
    renamed = RENAMED_SOURCE_REPOS.get(f"{org}/{repo}".lower())
    if renamed is None:
        return url
    return f"{prefix}{renamed}{sep}{path}"


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
            BiolinkClasses=set(row.get('Biolink Classes', '').split('|')),
            Prefixes=set(row.get('Prefixes', '').split('|')),
            Source=row.get('Source', ''),
            SourceURL=current_source_url(row.get('Source URL', '')),
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

