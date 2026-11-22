"""Run the BabelTest assertions in GitHub issues and report the results, without pytest.

This is the layer that the pytest suite (tests/github_issues/test_github_issues.py) and any
other tool share, such as a UI that runs every issue's tests against a chosen NodeNorm/NameRes
pair. It owns the expectation rules:

- An **open** issue is expected to fail. If its tests now all pass, it is **closeable**.
- A **closed** issue is expected to pass. If its tests now fail, it should be **reopened**.

Typical use::

    from babel_validation import CachedNameRes, CachedNodeNorm, GitHubIssuesTestCases, run_issue_tests

    cases = GitHubIssuesTestCases(token, ["NCATSTranslator/Babel"])
    reports = run_issue_tests(
        cases,
        nodenorm=CachedNodeNorm.from_url("https://nodenorm.transltr.io/"),
        nameres=CachedNameRes.from_url("https://name-lookup.transltr.io/"),
    )
    for r in reports:
        if r.closeable:
            print(f"{r.issue_id} now passes; consider closing it ({r.url})")
        elif r.reopened:
            print(f"{r.issue_id} fails again; consider reopening it ({r.url})")

Messages in a report come from issue bodies and service responses, both untrusted: format
them with ``!r`` before they reach a terminal or a web page (see AGENTS.md, "Untrusted Input").
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from babel_validation.core.testrow import TestResult, TestStatus
from babel_validation.services.nameres import NameResService
from babel_validation.services.nodenorm import NodeNormService
from babel_validation.sources.github.github_issues_test_cases import (
    Assertion,
    GitHubIssuesTestCases,
    issue_id,
)


@dataclass(frozen=True)
class ResultRecord:
    """One TestResult, with the name of the assertion that produced it."""

    assertion: str
    result: TestResult

    @property
    def status(self) -> TestStatus:
        return self.result.status

    @property
    def message(self) -> str:
        return self.result.message


@dataclass
class IssueReport:
    """The outcome of running every assertion found in one issue."""

    issue_id: str
    url: str
    state: str  # "open" or "closed"
    results: list[ResultRecord] = field(default_factory=list)
    # Assertion names that match no handler: a mistake in the issue, never a pass.
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
        """True if something ran and nothing failed. Skipped results count as neither."""
        return bool(self.results) and not self.has_failures

    @property
    def closeable(self) -> bool:
        """An open issue whose tests all pass, with no unknown assertion names."""
        return self.is_open and self.all_passed and not self.unknown_assertions

    @property
    def reopened(self) -> bool:
        """A closed issue with a failing test."""
        return not self.is_open and self.has_failures


def run_assertions(
    issue_id: str,
    url: str,
    state: str,
    assertions: Iterable[Assertion],
    *,
    nodenorm: NodeNormService,
    nameres: NameResService,
    pass_if_found_in_top: int = 5,
) -> IssueReport:
    """Run every assertion from one issue and collect the results into an IssueReport.

    An unknown assertion name is recorded in ``unknown_assertions`` rather than raised, so the
    caller decides how loudly to report it: the pytest suite fails the issue's test. An
    exception from a service (an outage, an HTTP error) is not caught: a report built around one
    would read as the issue's own result.
    """
    report = IssueReport(issue_id=issue_id, url=url, state=state)
    for assertion in assertions:
        if not assertion.is_known:
            report.unknown_assertions.append(assertion.assertion)
            continue
        for result in assertion.run(nodenorm, nameres, pass_if_found_in_top):
            report.results.append(ResultRecord(assertion=assertion.assertion, result=result))
    return report


def run_issue_tests(
    test_cases: GitHubIssuesTestCases,
    repos=None,
    *,
    nodenorm: NodeNormService,
    nameres: NameResService,
    pass_if_found_in_top: int = 5,
    issue_ids: list[str] | None = None,
) -> list[IssueReport]:
    """Fetch the issues that carry BabelTests, run them, and return one IssueReport per issue.

    :param test_cases: a configured GitHubIssuesTestCases, which holds the GitHub token and the
        repositories to search.
    :param repos: a subset of those repositories to search; all of them by default.
    :param issue_ids: specific issues ("org/repo#N"), which skips the search and with it the
        search index's lag. They must be in a repository test_cases was configured with.
    """
    if issue_ids:
        issues = test_cases.get_issues_by_ids(issue_ids)
    else:
        issues = test_cases.get_issues_with_tests(repos)

    return [
        run_assertions(
            issue_id(issue),
            issue.html_url,
            issue.state,
            test_cases.get_test_issues_from_issue(issue),
            nodenorm=nodenorm,
            nameres=nameres,
            pass_if_found_in_top=pass_if_found_in_top,
        )
        for issue in issues
    ]
