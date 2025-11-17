#!/usr/bin/env python3
#
# test_non_deterministic_results.py - Test whether NodeNorm results are non-deterministic.
#
# This has been reported in a bunch of issues:
#   - https://github.com/NCATSTranslator/NameResolution/issues/220
#
import json

import pytest
import requests
import deepdiff


# We've been told that these queries are sometimes non-deterministic.
non_deterministic_queries = [
    [ # From https://github.com/NCATSTranslator/NameResolution/issues/220
        "MONDO:0018908",
        "UMLS:C2911293",
    ],
]

@pytest.mark.parametrize("non_deterministic_query", non_deterministic_queries)
def test_non_deterministic_results(target_info, non_deterministic_query, repeat_count=100):
    """
    Test a list of non-deterministic queries by ensuring that repeated requests
    to the normalization endpoint return consistent results. The first response
    for each query is assumed to be the "correct" result, and any differences
    in subsequent responses are noted.

    :param target_info: Dictionary containing information about the target API.
                        Must include the key 'NodeNormURL', which provides the
                        base URL for the NodeNorm service.
    :type target_info: dict
    :param non_deterministic_query: The query to be sent repeatedly to verify
                                     consistency in the API's results.
    :type non_deterministic_query: str
    :param repeat_count: Number of times to repeat the same query. Defaults to 100.
    :type repeat_count: int
    :return: None
    :raises AssertionError: If the results of repeated queries differ, indicating
                            non-determinism in the endpoint responses.
    """
    nodenorm_normalize_url = target_info['NodeNormURL'] + 'get_normalized_nodes'
    nodenorm_query = {
        'curies': non_deterministic_query,
        'conflate': 'true',
        'drug_chemical_conflate': 'true',
        'individual_types': 'true',
    }

    # Here's what we're going to do:
    #   1. For each query, repeat the query up to repeat_count.
    #   2. Assume the first result is "correct", then record the diffs for each subsequent query.
    first_response = None
    diffs = []

    for index in range(repeat_count):
        result = requests.post(nodenorm_normalize_url, json=nodenorm_query)
        result.raise_for_status()
        response = result.json()

        if first_response is None:
            first_response = response
            print(f"Found first response for comparison: {json.dumps(first_response, indent=2)}")
            continue

        diffs.append(deepdiff.DeepDiff(first_response, response, ignore_order=True))

    any_failures = any(diffs)
    if not any_failures:
        assert True, f"All {repeat_count} queries of {non_deterministic_query} returned the same results."
    else:
        assert diffs == [{} for _ in range(repeat_count - 1)]
