#!/usr/bin/env python3
#
# test_non_deterministic_results.py - Test whether NameRes results are non-deterministic.
#
# This has been reported in a bunch of issues:
#   - https://github.com/NCATSTranslator/NameResolution/issues/220
#
import pytest
import requests
import deepdiff


# We've been told that these queries are sometimes non-deterministic.
non_deterministic_queries = [
    "Non-Hodgkin lymphomas",            # From https://github.com/NCATSTranslator/NameResolution/issues/220
]

@pytest.mark.parametrize("non_deterministic_query", non_deterministic_queries)
def test_non_deterministic_results(target_info, non_deterministic_query, repeat_count=100):
    """
    Tests non-deterministic query results by executing a query multiple times and comparing
    responses for consistency. The test assumes that the first response is the "correct" one
    and compares all subsequent results to it. Successful execution implies consistent
    responses across all repeated queries.

    :param target_info: Dictionary containing the target environment configuration. Must
        include a 'NameResURL' key specifying the base URL for the name resolution service.
    :type target_info: dict

    :param non_deterministic_query: Query string to be tested for determinism in results.
    :type non_deterministic_query: str

    :param repeat_count: Number of times the query should be repeated for comparison.
        Defaults to 100.
    :type repeat_count: int

    :return: None. Asserts if all responses match the first one or fail otherwise.
    """
    nameres_lookup_url = target_info['NameResURL'] + 'lookup'
    nameres_query = {
        'string': non_deterministic_query,
        'autocomplete': 'false',
        'limit': 100,
    }

    # Here's what we're going to do:
    #   1. For each query, repeat the query up to repeat_count.
    #   2. Assume the first result is "correct", then record the diffs for each subsequent query.
    first_response = None
    diffs = []

    for index in range(repeat_count):
        result = requests.post(nameres_lookup_url, params=nameres_query)
        result.raise_for_status()
        response = result.json()

        if first_response is None:
            first_response = response
            continue

        diffs.append(deepdiff.DeepDiff(first_response, response, ignore_order=True))

    any_failures = any(diffs)
    if not any_failures:
        assert True, f"All {repeat_count} queries of '{non_deterministic_query}' returned the same results."
    else:
        assert diffs == [{} for _ in range(repeat_count - 1)]