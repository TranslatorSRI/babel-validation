import itertools
import time
import urllib.parse
import requests
import pytest
from common.google_sheet_test_cases import GoogleSheetTestCases, TestRow

# We generate a set of tests from the GoogleSheetTestCases.
gsheet = GoogleSheetTestCases()


@pytest.mark.parametrize("test_row", gsheet.test_rows)
def test_normalization(target_info, test_row, test_category):
    """
    Test normalization on NodeNorm.

    :param target_info: The target information to test.
    :param test_row: The TestRow to test.
    :param test_category: A function that accepts a category name and
    :return: The number of queries executed.
    """
    count_queries = 0

    nodenorm_url = target_info['NodeNormURL']

    category = test_row.Category
    if not test_category(category):
        pytest.skip(f"Skipping category {category} because of the category filter.")

    source = test_row.Source
    source_url = test_row.SourceURL
    source_info = f"{source} ({source_url})"

    preferred_label = test_row.PreferredLabel

    expected_id = test_row.PreferredID
    query_ids = {test_row.QueryID}
    query_ids.add(test_row.PreferredID)
    query_ids.update(test_row.AdditionalIDs)

    # Test these labels against NameRes
    for query_id in query_ids:
        if not query_id:
            continue

        nodenorm_url_lookup = urllib.parse.urljoin(nodenorm_url, 'get_normalized_nodes')
        request = {
            "curie": [query_id]
        }
        if test_row.Conflations:
            leftover_conflations = test_row.Conflations
            leftover_conflations.remove('')
            if 'gene_protein' in test_row.Conflations:
                request['conflate'] = 'true'
                leftover_conflations.remove('gene_protein')
            if 'drug_chemical' in test_row.Conflations:
                request['drug_chemical_conflate'] = 'true'
                leftover_conflations.remove('drug_chemical')
            assert leftover_conflations == set(), f"Unknown conflations in for {test_row}: {leftover_conflations}"

        test_summary = f"Queried {query_id} ({preferred_label}) on {nodenorm_url_lookup}"
        response = requests.get(nodenorm_url_lookup, request)
        count_queries += 1

        assert response.ok, f"Could not send request {request} to GET {nodenorm_url_lookup}: {response}"
        results = response.json()

        assert query_id in results, f"{test_summary} but no result returned for {query_id} in results: {results}"
        result = results[query_id]

        if not result:
            if 'negative' in test_row.Flags:
                assert not result, f"{test_summary} not found in NodeNorm as expected."
            else:
                assert result, f"{test_summary} but NodeNorm could not normalize {query_id} and returned null"

        assert 'id' in result, f"{test_summary} but no 'id' in result: {result}"

        # Test preferred identifier
        assert result['id']['identifier'] == expected_id,\
            (f"{test_summary} but normalized to {result['id']['identifier']} ({result['id']['label']}), not expected "
             f"identifier {expected_id}.")

        # Test preferred label
        if test_row.PreferredLabel:
            assert result['id']['label'] == preferred_label,\
                f"{test_summary} but preferred label is {result['id']['label']}, not expected label {preferred_label}."

        # Test Biolink types
        biolink_types = result['type']
        for biolink_type in test_row.BiolinkClasses:
            if not biolink_type:
                continue
            elif biolink_type.startswith('!'):
                biolink_type = biolink_type[1:]
                assert biolink_type not in set(biolink_types), (f"{test_summary} excluded biolink type {biolink_type} "
                                                                f"found in types: {biolink_types}")
            else:
                assert biolink_type in set(biolink_types), (f"{test_summary} biolink type {biolink_type} not found in "
                                                            f"types: {biolink_types}")

    return count_queries


@pytest.mark.parametrize("category_and_expected_times", [
    # We expect unit tests to run in less than half a second each query and name.
    {'category': 'Unit Tests', 'expected_time_per_query': 0.2},
])
def test_normalization_rates(target_info, category_and_expected_times):
    """
    This is being done in service of https://github.com/TranslatorSRI/NodeNormalization/issues/205

    To ensure that we can handle 20 simultaneous queries within 10 seconds, we will run a set of
    rows from the Google Sheet, and measure the rate at which we process those queries.

    :param target_info: The target_info object (really a config object).
    """

    category = category_and_expected_times['category']
    rows_to_test = list(filter(lambda row: row.Category == category, gsheet.test_rows))
    assert len(rows_to_test) > 0, f"Category '{category}' not found in Google Sheet {gsheet}."

    time_started = time.time_ns()
    count_queries = 0
    for row in rows_to_test:
        count_queries += test_normalization(target_info, row, lambda cat: True)
    time_ended = time.time_ns()
    time_taken = time_ended - time_started
    time_taken_secs = float(time_taken) / 1e+9

    time_per_test_row = time_taken_secs / len(rows_to_test)
    time_per_query = time_taken_secs / count_queries
    print(f"NodeNorm took {time_taken_secs:.3f} seconds to process {len(rows_to_test)} test rows " +
          f"({time_per_test_row:.3f} seconds/test row, {time_per_query:.3f} seconds/query) on {target_info}")

    assert len(rows_to_test) > 20, f"Categories with fewer than twenty test rows are not likely to be representative."
    assert count_queries > 20, f"Categories with fewer than twenty queries are not likely to be representative."

    if 'expected_time_per_query' in category_and_expected_times:
        assert time_per_query < category_and_expected_times['expected_time_per_query']
