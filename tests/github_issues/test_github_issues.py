import json

import pytest

from babel_validation.assertions import ASSERTION_HANDLERS
from babel_validation.services.nameres import CachedNameRes
from babel_validation.services.nodenorm import CachedNodeNorm
from babel_validation.core.testrow import TestResult, TestStatus
from babel_validation.runner import run_assertions


class OpenIssueMarkerAbsorbsNothing(AssertionError):
    """
    Never raised: the ``raises=`` for the strict xfail on an open issue.

    That marker has one job, turning an open issue whose assertions all pass into a strict
    XPASS failure, which says the issue looks closeable. An open issue whose assertions fail
    is reported by the imperative ``pytest.xfail()`` at the end of the test, which pytest
    handles before it looks at the marker's ``raises=``. Without ``raises=``, a strict xfail
    also absorbs any exception, so a NodeNorm outage, an HTTP 500 or a bug in our own parsing
    reported XFAIL, and every open issue went green. Naming an exception that nothing raises
    lets every such exception fail the test.
    """


def test_github_issue(request, target_info, github_issue_id, github_issue, github_issues_test_cases, subtests):
    nodenorm = CachedNodeNorm.from_url(target_info['NodeNormURL'])
    nameres = CachedNameRes.from_url(target_info['NameResURL'])
    # NameRes assertions pass if the expected CURIE is in the top N results; N
    # comes from targets.ini (NameResXFailIfInTop) rather than being hardcoded.
    pass_if_found_in_top = int(target_info.get('NameResXFailIfInTop', 5))
    tests = github_issues_test_cases.get_test_issues_from_issue(github_issue)
    if not tests:
        pytest.skip(f"No tests found in issue {github_issue}")
        return

    is_open = github_issue.state == "open"

    # Unknown assertion types must fail hard, not XFAIL, and before anything is run.
    unknown = [f"'{t.assertion}'" for t in tests if not t.is_known]
    if unknown:
        pytest.fail(
            f"Issue {github_issue_id} uses unknown assertion type(s): "
            f"{', '.join(unknown)} with param sets {json.dumps([t.param_sets for t in tests])}. "
            f"Valid types (case-insensitive): {sorted(ASSERTION_HANDLERS.keys())}"
        )

    # Open issues are assumed to fail, so we set an xfail marker (but we set it to strict so
    # that XPASSes are reported loudly). raises= keeps it from absorbing an outage: see
    # OpenIssueMarkerAbsorbsNothing.
    if is_open:
        request.node.add_marker(pytest.mark.xfail(
            reason=f"Issue {github_issue.html_url} is expected to fail because the issue is open.",
            raises=OpenIssueMarkerAbsorbsNothing,
            strict=True,
        ))

    # The library decides what passed and what the issue's state implies (closeable,
    # reopened); this test only maps that report onto pytest outcomes.
    report = run_assertions(github_issue_id, github_issue.html_url, github_issue.state, tests,
                            nodenorm=nodenorm, nameres=nameres, pass_if_found_in_top=pass_if_found_in_top)

    # For open issues: xfail so the result stays in the xfail family. Don't assert inside
    # subtests for them: subtest failures don't respect the xfail marker on the parent test,
    # so they would be reported as real failures.
    # - Some assertions failed → xfail with a count summary (expected outcome).
    # - All assertions passed  → the xfail marker added above makes this XPASS,
    #   which (strict=True) reports as a failure and signals the issue is closeable.
    # - No assertions ran      → xfail as a configuration error.
    if report.is_open:
        if not report.results:
            pytest.xfail(f"Open issue {github_issue_id} produced no test results — check assertion configuration")
        elif report.has_failures:
            failed_messages = [f"{github_issue_id} ({github_issue.state}): {r.message}" for r in report.failed_results]
            pct = len(failed_messages) / len(report.results)
            details = "\n".join(failed_messages[:5])
            if len(failed_messages) > 5:
                details += f"\n... and {len(failed_messages) - 5} more"
            pytest.xfail(
                f"Open issue {github_issue_id} has {len(failed_messages):,} failing assertions "
                f"out of {len(report.results):,} ({pct:.0%}):\n{details}"
            )
        return

    for record in report.results:
        with subtests.test(msg=github_issue_id):
            match record.result:
                case TestResult(status=TestStatus.Passed, message=message):
                    assert True, f"{github_issue_id} ({github_issue.state}): {message}"

                case TestResult(status=TestStatus.Failed, message=message):
                    assert False, f"{github_issue_id} ({github_issue.state}): {message}"

                case TestResult(status=TestStatus.Skipped, message=message):
                    pytest.skip(f"{github_issue_id} ({github_issue.state}): {message}")

                case _:
                    assert False, f"Unknown result from {github_issue_id}: {record.result}"
