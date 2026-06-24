import pytest

from babel_validation.assertions import ASSERTION_HANDLERS
from babel_validation.runner import run_assertions
from babel_validation.services.nameres import CachedNameRes
from babel_validation.services.nodenorm import CachedNodeNorm
from babel_validation.core.testrow import TestStatus


def test_github_issue(request, target_info, github_issue_id, github_issue, github_issues_test_cases, subtests):
    """Thin adapter around babel_validation.runner.run_assertions.

    The library decides what each result *is* (pass/fail) and what the issue state *implies*
    (open ⇒ expected-fail, closed ⇒ expected-pass); this function only maps the resulting
    IssueReport onto pytest outcomes (xfail / subtests / skip / fail)."""
    nodenorm = CachedNodeNorm.from_url(target_info['NodeNormURL'])
    nameres = CachedNameRes.from_url(target_info['NameResURL'])
    # NameRes assertions pass if the expected CURIE is in the top N results; N
    # comes from targets.ini (NameResXFailIfInTop) rather than being hardcoded.
    pass_if_found_in_top = int(target_info.get('NameResXFailIfInTop', 5))

    assertions = github_issues_test_cases.get_test_issues_from_issue(github_issue)
    if not assertions:
        pytest.skip(f"No tests found in issue {github_issue_id}")

    report = run_assertions(
        github_issue_id, github_issue.html_url, github_issue.state, assertions,
        nodenorm=nodenorm, nameres=nameres, pass_if_found_in_top=pass_if_found_in_top,
    )

    # Unknown assertion types must fail hard, not XFAIL.
    if report.unknown_assertions:
        unknown = ", ".join(f"'{a}'" for a in report.unknown_assertions)
        pytest.fail(
            f"Issue {github_issue_id} uses unknown assertion type(s): {unknown}. "
            f"Valid types (case-insensitive): {sorted(ASSERTION_HANDLERS.keys())}"
        )

    # Open issues are assumed to fail, so we set a strict xfail marker (so XPASSes — issues that
    # now pass and are therefore closeable — are reported loudly).
    if report.is_open:
        request.node.add_marker(pytest.mark.xfail(
            reason=f"Issue {report.url} is expected to fail because the issue is open.",
            strict=True,
        ))

    if not report.is_open:
        # Closed issue: assert each result in its own subtest.
        for r in report.results:
            with subtests.test(msg=github_issue_id):
                if r.status == TestStatus.Passed:
                    assert True, f"{github_issue_id} ({report.state}): {r.message}"
                elif r.status == TestStatus.Failed:
                    assert False, f"{github_issue_id} ({report.state}): {r.message}"
                elif r.status == TestStatus.Skipped:
                    pytest.skip(f"{github_issue_id} ({report.state}): {r.message}")
                else:
                    assert False, f"Unknown result from {github_issue_id}: {r.result}"
        return

    # Open issue: keep the result in the xfail family.
    # - No results        → xfail as a configuration error.
    # - Some failures     → xfail with a count summary (the expected outcome).
    # - All passed        → the strict xfail marker above makes this XPASS, reported as a
    #                       failure, signaling the issue is closeable.
    if not report.results:
        pytest.xfail(f"Open issue {github_issue_id} produced no test results — check assertion configuration")
    failed = report.failed_results
    if failed:
        details = "\n".join(f"{github_issue_id} ({report.state}): {r.message}" for r in failed[:5])
        if len(failed) > 5:
            details += f"\n... and {len(failed) - 5} more"
        pct = len(failed) / len(report.results)
        pytest.xfail(
            f"Open issue {github_issue_id} has {len(failed):,} failing assertions "
            f"out of {len(report.results):,} ({pct:.0%}):\n{details}"
        )
