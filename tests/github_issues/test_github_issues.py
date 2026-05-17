import itertools
import json

import pytest

from src.babel_validation.assertions import ASSERTION_HANDLERS
from src.babel_validation.services.nameres import CachedNameRes
from src.babel_validation.services.nodenorm import CachedNodeNorm
from src.babel_validation.core.testrow import TestResult, TestStatus


def test_github_issue(request, target_info, github_issue_id, github_issue, github_issues_test_cases, subtests):
    nodenorm = CachedNodeNorm.from_url(target_info['NodeNormURL'])
    nameres = CachedNameRes.from_url(target_info['NameResURL'])
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
    count_subtests_failed = 0
    for test_issue in tests:
        results_nodenorm = test_issue.test_with_nodenorm(nodenorm)
        results_nameres = test_issue.test_with_nameres(nodenorm, nameres)

        for result in itertools.chain(results_nodenorm, results_nameres):
            count_subtests += 1

            with subtests.test(msg=github_issue_id):
                match result:
                    case TestResult(status=TestStatus.Passed, message=message):
                        assert True, f"{github_issue_id} ({github_issue.state}): {message}"

                    case TestResult(status=TestStatus.Failed, message=message):
                        count_subtests_failed += 1
                        if is_open:
                            pytest.xfail(message)
                        else:
                            assert False, f"{github_issue_id} ({github_issue.state}): {message}"

                    case TestResult(status=TestStatus.Skipped, message=message):
                        pytest.skip(f"{github_issue_id} ({github_issue.state}): {message}")

                    case _:
                        assert False, f"Unknown result from {github_issue_id}: {result}"

    # For open issues: xfail so the result stays in the xfail family.
    # - Some subtests failed → xfail with a count summary (expected outcome).
    # - All subtests passed  → the xfail marker added above makes this XPASS,
    #   which (strict=True) reports as a failure and signals the issue is closeable.
    # - No subtests ran      → xfail as a configuration error.
    if is_open:
        if count_subtests == 0:
            pytest.xfail(f"Open issue {github_issue_id} produced no test results — check assertion configuration")
        elif count_subtests_failed > 0:
            pct = count_subtests_failed / count_subtests
            pytest.xfail(
                f"Open issue {github_issue_id} has {count_subtests_failed:,} failing subtests "
                f"out of {count_subtests:,} ({pct:.0%})"
            )
