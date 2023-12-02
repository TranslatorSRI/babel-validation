import logging
import time
import urllib.parse
import requests
import pytest
from common.google_sheet_test_cases import GoogleSheetTestCases, TestRow

# We generate a set of tests from the GoogleSheetTestCases.
gsheet = GoogleSheetTestCases()


@pytest.mark.parametrize("test_row", gsheet.test_rows)
def test_label(target_info, test_row, test_category):
    """
    :param target_info: The target_info object (really a config object).
    :param test_row: A test row to be tested.
    :param test_category: A function that can be called with a category name to determine whether or not a particular
        category should be tested.
    :return: The number of queries generated.
    """

    count_queries = 0

    nameres_url = target_info['NameResURL']
    limit = target_info['NameResLimit']
    nameres_xfail_if_in_top = int(target_info['NameResXFailIfInTop'])

    category = test_row.Category
    if not test_category(category):
        pytest.skip(f"Skipping category {category} because of the category filter.")

    source = test_row.Source
    source_url = test_row.SourceURL
    source_info = f"{source} ({source_url})"

    biolink_classes = test_row.BiolinkClasses
    # Make sure we test this without Biolink classes as well
    if '' not in biolink_classes:
        biolink_classes.append('')

    expected_id = test_row.PreferredID
    query_labels = {test_row.QueryLabel}
    query_labels.add(test_row.PreferredLabel)
    query_labels.update(test_row.AdditionalLabels)

    # Test these labels against NameRes
    for query_label in query_labels:
        label = query_label.strip()
        if not label:
            continue

        for biolink_class in biolink_classes:
            biolink_class_exclude = ''
            if biolink_class.startswith('!'):
                biolink_class_exclude = biolink_class[1:]
                biolink_class = ''

            nameres_url_lookup = urllib.parse.urljoin(nameres_url, 'lookup')
            request = {
                "string": label,
                "biolink_type": biolink_class,
                "limit": limit
            }
            if test_row.Prefixes:
                request['only_prefixes'] = "|".join(list(test_row.Prefixes))

            test_summary = f"querying {nameres_url_lookup} with label '{label}' and biolink_type {biolink_class}"
            response = requests.get(nameres_url_lookup, request)
            count_queries += 1

            assert response.ok, f"Could not send request {request} to GET {nameres_url_lookup}: {response}"
            results = response.json()

            # All curies
            all_curies = list(map(lambda r: r['curie'], results))

            # Check for negative results
            if 'negative' in test_row.Flags:
                if not results:
                    assert not results, f"Negative test {test_summary} successful: no results found."
                    continue

                if expected_id in all_curies:
                    expected_index = all_curies.index(expected_id)
                    assert expected_id not in all_curies, \
                        f"Negative test {test_summary} found expected CURIE {expected_id} in top {limit} results: {results[expected_index]}"
                else:
                    assert expected_id not in all_curies, f"Negative test {test_summary} did not find expected ID {expected_id} in top {limit} results."

                return count_queries

            # There are three possible responses:
            if not results:
                # 1. We got back no results.
                pytest.fail(f"No results for {test_summary} from {source_info}")
            elif expected_id == '':
                pytest.fail(f"No expected CURIE for {test_summary} from {source_info}: best result is {results[0]}")
            elif results[0]['curie'] == expected_id:
                top_result = results[0]
                assert top_result['curie'] == expected_id, \
                    f"{test_summary} returned expected ID {expected_id} as top result"

                # Additionally, test the biolink_class_exclude field if there is one.
                if biolink_class_exclude:
                    assert biolink_class_exclude not in top_result['types'], \
                        f"Biolink types for {top_result['curie']} are {top_result['types']}, which includes {biolink_class_exclude} which should be excluded."

            elif expected_id in all_curies:
                expected_index = all_curies.index(expected_id)

                fail_message = f"{test_summary} returns {results[0]['curie']} ('{results[0]['label']}') as the " \
                               f"top result, but {expected_id} is at {expected_index} index."
                if expected_index <= nameres_xfail_if_in_top:
                    pytest.xfail(fail_message)
                else:
                    pytest.fail(fail_message)
            else:
                pytest.fail(f"{test_summary} but expected result {expected_id} not found: {results}")

    return count_queries


@pytest.mark.parametrize("category_and_expected_times", [
    # We expect unit tests to run in less than half a second each query and name.
    {'category': 'Unit Tests', 'expected_time_per_query': 0.5},
    {'category': 'Slow Tests', 'expected_time_per_query': 1},
])
def test_query_rates(target_info, category_and_expected_times):
    """
    This is being done in service of https://github.com/TranslatorSRI/NameResolution/issues/113

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
        count_queries += test_label(target_info, row, lambda cat: True)
    time_ended = time.time_ns()
    time_taken = time_ended - time_started
    time_taken_secs = float(time_taken) / 1e+9

    time_per_test_row = time_taken_secs / len(rows_to_test)
    time_per_query = time_taken_secs / count_queries
    print(f"NameRes took {time_taken_secs:.3f} seconds to process {len(rows_to_test)} test rows " +
          f"({time_per_test_row:.3f} seconds/test row, {time_per_query:.3f} seconds/query) on {target_info}")

    assert len(rows_to_test) > 20, f"Categories with fewer than twenty test rows are not likely to be representative."
    assert count_queries > 20, f"Categories with fewer than twenty queries are not likely to be representative."

    if 'expected_time_per_query' in category_and_expected_times:
        assert time_per_query < category_and_expected_times['expected_time_per_query']
