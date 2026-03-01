import itertools
import json

import pytest

from src.babel_validation.assertions import ASSERTION_HANDLERS
from src.babel_validation.services.nameres import CachedNameRes
from src.babel_validation.services.nodenorm import CachedNodeNorm
from src.babel_validation.core.testrow import TestResult, TestStatus


def test_github_issue(request, target_info, github_issue, github_issues_test_cases_fixture, subtests):
    nodenorm = CachedNodeNorm.from_url(target_info['NodeNormURL'])
    nameres = CachedNameRes.from_url(target_info['NameResURL'])
    tests = github_issues_test_cases_fixture.get_test_issues_from_issue(github_issue)
    if not tests:
        pytest.skip(f"No tests found in issue {github_issue}")
        return

    parts = github_issue.html_url.split('/')
    issue_id = f"{parts[3]}/{parts[4]}#{github_issue.number}"
    is_open = github_issue.state == "open"

    # Unknown assertion types must fail hard, not XFAIL.
    unknown = [f"'{t.assertion}'" for t in tests
               if t.assertion.lower() not in ASSERTION_HANDLERS]
    if unknown:
        pytest.fail(
            f"Issue {issue_id} uses unknown assertion type(s): "
            f"{', '.join(unknown)} with param sets {json.dumps([t.param_set for t in tests])}. "
            f"Valid types (case-insensitive): {sorted(ASSERTION_HANDLERS.keys())}"
        )

    # Open issues are expected to have failing tests. Mark as xfail(strict=False) so
    # that if all subtests pass, the parent shows as XPASS (X) — issue ready to close.
    if is_open:
        request.node.add_marker(pytest.mark.xfail(
            reason=f"Issue {issue_id} is still open",
            strict=False,
        ))

    count_subtests = 0
    count_subtests_xfailed = 0
    for test_issue in tests:
        results_nodenorm = test_issue.test_with_nodenorm(nodenorm)
        results_nameres = test_issue.test_with_nameres(nodenorm, nameres)

        for result in itertools.chain(results_nodenorm, results_nameres):
            count_subtests += 1

            with subtests.test(msg=issue_id):
                match result:
                    case TestResult(status=TestStatus.Passed, message=message):
                        assert True, f"{issue_id} ({github_issue.state}): {message}"

                    case TestResult(status=TestStatus.Failed, message=message):
                        if is_open:
                            count_subtests_xfailed += 1
                            pytest.xfail(message)
                        else:
                            assert False, f"{issue_id} ({github_issue.state}): {message}"

                    case TestResult(status=TestStatus.Skipped, message=message):
                        pytest.skip(f"{issue_id} ({github_issue.state}): {message}")

                    case _:
                        assert False, f"Unknown result from {issue_id}: {result}"

    # If any subtest xfailed, also xfail the parent — otherwise the parent would show
    # as XPASS (masking the distinction between "all pass" and "some fail").
    if is_open and (count_subtests_xfailed > 0):
        pytest.xfail(f"Open issue {issue_id} has {count_subtests_xfailed:,} failing subtests out of {count_subtests:,} ({count_subtests_xfailed/count_subtests:.0%})")
