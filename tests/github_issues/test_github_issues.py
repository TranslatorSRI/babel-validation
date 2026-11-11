import itertools
import json

import pytest

from babel_validation.assertions import ASSERTION_HANDLERS
from babel_validation.services.nameres import CachedNameRes
from babel_validation.services.nodenorm import CachedNodeNorm
from babel_validation.core.testrow import TestResult, TestStatus


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

    # Unknown assertion types must fail hard, not XFAIL.
    unknown = [f"'{t.assertion}'" for t in tests
               if t.assertion.lower() not in ASSERTION_HANDLERS]
    if unknown:
        pytest.fail(
            f"Issue {github_issue_id} uses unknown assertion type(s): "
            f"{', '.join(unknown)} with param sets {json.dumps([t.param_sets for t in tests])}. "
            f"Valid types (case-insensitive): {sorted(ASSERTION_HANDLERS.keys())}"
        )

    # Open issues are assumed to fail, so we set an xfail marker (but we set it to strict so
    # that XPASSes are reported loudly).
    if is_open:
        request.node.add_marker(pytest.mark.xfail(
            reason=f"Issue {github_issue.html_url} is expected to fail because the issue is open.",
            strict=True,
        ))

    count_subtests = 0
    failed_messages = []
    for test_issue in tests:
        results_nodenorm = test_issue.test_with_nodenorm(nodenorm)
        results_nameres = test_issue.test_with_nameres(nodenorm, nameres, pass_if_found_in_top)

        for result in itertools.chain(results_nodenorm, results_nameres):
            count_subtests += 1

            if is_open:
                # Don't assert inside subtests for open issues: subtest failures
                # don't respect the xfail marker on the parent test, so they would
                # be reported as real failures. Collect them and xfail below instead.
                if result.status == TestStatus.Failed:
                    failed_messages.append(f"{github_issue_id} ({github_issue.state}): {result.message}")
                continue

            with subtests.test(msg=github_issue_id):
                match result:
                    case TestResult(status=TestStatus.Passed, message=message):
                        assert True, f"{github_issue_id} ({github_issue.state}): {message}"

                    case TestResult(status=TestStatus.Failed, message=message):
                        assert False, f"{github_issue_id} ({github_issue.state}): {message}"

                    case TestResult(status=TestStatus.Skipped, message=message):
                        pytest.skip(f"{github_issue_id} ({github_issue.state}): {message}")

                    case _:
                        assert False, f"Unknown result from {github_issue_id}: {result}"

    # For open issues: xfail so the result stays in the xfail family.
    # - Some assertions failed → xfail with a count summary (expected outcome).
    # - All assertions passed  → the xfail marker added above makes this XPASS,
    #   which (strict=True) reports as a failure and signals the issue is closeable.
    # - No assertions ran      → xfail as a configuration error.
    if is_open:
        if count_subtests == 0:
            pytest.xfail(f"Open issue {github_issue_id} produced no test results — check assertion configuration")
        elif failed_messages:
            pct = len(failed_messages) / count_subtests
            details = "\n".join(failed_messages[:5])
            if len(failed_messages) > 5:
                details += f"\n... and {len(failed_messages) - 5} more"
            pytest.xfail(
                f"Open issue {github_issue_id} has {len(failed_messages):,} failing assertions "
                f"out of {count_subtests:,} ({pct:.0%}):\n{details}"
            )
