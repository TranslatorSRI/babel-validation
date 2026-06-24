"""Run GitHub-issue BabelTest assertions and report results — independent of pytest.

This is the orchestration layer shared by Babel Explorer (run every issue test against a chosen
NodeNorm/NameRes pair and show which passed/failed and why) and this repo's own pytest suite.

It owns the *expectation rules*:

- An **open** issue is expected to fail. If its tests now all pass, the issue is **closeable**.
- A **closed** issue is expected to pass. If its tests now fail, the issue should be **reopened**.

Typical use::

    from babel_validation import (
        GitHubIssuesTestCases, CachedNodeNorm, CachedNameRes, run_issue_tests,
    )

    cases = GitHubIssuesTestCases(token, repos)
    reports = run_issue_tests(
        cases,
        nodenorm=CachedNodeNorm.from_url("https://nodenorm.transltr.io/"),
        nameres=CachedNameRes.from_url("https://name-lookup.transltr.io/"),
    )
    for r in reports:
        if r.closeable:
            print(f"{r.issue_id} now passes — consider closing ({r.url})")
        elif r.reopened:
            print(f"{r.issue_id} regressed — consider reopening ({r.url})")
            for failure in r.failed_results:
                print(f"    {failure.assertion} {failure.param_set}: {failure.message}")
"""

from dataclasses import dataclass, field
from typing import Iterable

from babel_validation.core.testrow import TestResult, TestStatus
from babel_validation.services.nameres import CachedNameRes
from babel_validation.services.nodenorm import CachedNodeNorm
from babel_validation.sources.github.github_issues_test_cases import (
    Assertion,
    GitHubIssuesTestCases,
)


@dataclass(frozen=True)
class ResultRecord:
    """One TestResult with provenance back to the assertion + param_set that produced it."""

    assertion: str
    param_set: list[str]
    result: TestResult

    @property
    def status(self) -> TestStatus:
        return self.result.status

    @property
    def message(self) -> str:
        return self.result.message


@dataclass
class IssueReport:
    """The outcome of running every assertion found in one GitHub issue."""

    issue_id: str
    url: str
    state: str  # "open" | "closed"
    results: list[ResultRecord] = field(default_factory=list)
    # Assertion names that don't map to a known handler — a hard configuration error.
    unknown_assertions: list[str] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return self.state == "open"

    @property
    def failed_results(self) -> list[ResultRecord]:
        return [r for r in self.results if r.status == TestStatus.Failed]

    @property
    def has_failures(self) -> bool:
        return any(r.status == TestStatus.Failed for r in self.results)

    @property
    def all_passed(self) -> bool:
        return bool(self.results) and not self.has_failures

    @property
    def closeable(self) -> bool:
        """Open issue whose tests now all pass (and parse cleanly) — a candidate to close."""
        return self.is_open and self.all_passed and not self.unknown_assertions

    @property
    def reopened(self) -> bool:
        """Closed issue whose tests now fail — a candidate to reopen."""
        return (not self.is_open) and self.has_failures


def run_assertions(
    issue_id: str,
    url: str,
    state: str,
    assertions: Iterable[Assertion],
    *,
    nodenorm: CachedNodeNorm,
    nameres: CachedNameRes,
    pass_if_found_in_top: int = 5,
) -> IssueReport:
    """Run every assertion for a single issue and collect the results into an IssueReport.

    Unknown assertion names are recorded in ``unknown_assertions`` rather than raised, so the
    caller can decide how to surface them (the pytest suite fails hard; Explorer can flag them).
    """
    report = IssueReport(issue_id=issue_id, url=url, state=state)
    for assertion in assertions:
        if not assertion.is_known:
            report.unknown_assertions.append(assertion.assertion)
            continue
        for param_set, result in assertion.run(nodenorm, nameres, pass_if_found_in_top):
            report.results.append(
                ResultRecord(assertion=assertion.assertion, param_set=param_set, result=result)
            )
    return report


def run_issue_tests(
    test_cases: GitHubIssuesTestCases,
    repos=None,
    *,
    nodenorm: CachedNodeNorm,
    nameres: CachedNameRes,
    pass_if_found_in_top: int = 5,
    issue_ids: list[str] | None = None,
) -> list[IssueReport]:
    """Fetch issue tests and run them, returning one IssueReport per issue.

    :param test_cases: a configured ``GitHubIssuesTestCases`` (provides the GitHub auth + repos).
    :param repos: optional repo subset; defaults to the repos the test_cases was built with.
    :param issue_ids: optional explicit issue IDs ('org/repo#N', 'repo#N', or 'N'). When given,
                      only those issues are tested (and the GitHub search index lag is bypassed);
                      otherwise every issue containing BabelTest syntax is discovered and run.
    """
    if issue_ids:
        issues = test_cases.get_issues_by_ids(issue_ids)
    else:
        issues = test_cases.get_issues_with_tests(repos)

    reports = []
    for issue in issues:
        issue_id = f"{issue.repository.full_name}#{issue.number}"
        assertions = test_cases.get_test_issues_from_issue(issue)
        reports.append(
            run_assertions(
                issue_id,
                issue.html_url,
                issue.state,
                assertions,
                nodenorm=nodenorm,
                nameres=nameres,
                pass_if_found_in_top=pass_if_found_in_top,
            )
        )
    return reports
