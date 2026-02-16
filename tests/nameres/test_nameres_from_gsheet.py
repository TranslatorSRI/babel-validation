import urllib.parse
import requests
import pytest
from src.babel_validation.sources.google_sheet_test_cases import GoogleSheetTestCases

# Configuration options
NAMERES_TIMEOUT = 10 # If we don't get a response in 10 seconds, that's a fail.

# We generate a set of tests from the GoogleSheetTestCases.
gsheet = GoogleSheetTestCases()


@pytest.mark.parametrize("test_row", gsheet.test_rows('test_nameres_from_gsheet.test_label', test_nodenorm=False, test_nameres=True))
def test_label(target_info, test_row, test_category):
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
        biolink_classes.update('')

    expected_id = test_row.PreferredID
    query_labels = {test_row.QueryLabel}
    query_labels.add(test_row.PreferredLabel)
    query_labels.update(test_row.AdditionalLabels)

    # Test these labels against NameRes
    count_tested_labels = 0
    for query_label in query_labels:
        label = query_label.strip()
        if not label:
            continue

        for biolink_class in biolink_classes:
            biolink_class_exclude = ''
            if biolink_class.startswith('!'):
                biolink_class_exclude = biolink_class[1:]
                biolink_class = ''

            # Only turn on autocomplete if the autocomplete flag is on.
            autocomplete_flag = 'false'
            if 'autocomplete' in test_row.Flags:
                autocomplete_flag = 'true'

            nameres_url_lookup = urllib.parse.urljoin(nameres_url, 'lookup')
            request = {
                "string": label,
                "autocomplete": autocomplete_flag,
                "biolink_type": biolink_class,
                "limit": limit
            }
            if test_row.Prefixes:
                only_prefixes = []
                exclude_prefixes = []
                for prefix in test_row.Prefixes:
                    if prefix.startswith('^'):
                        exclude_prefixes.append(prefix[1:])
                    else:
                        only_prefixes.append(prefix)
                request['only_prefixes'] = "|".join(only_prefixes)
                request['exclude_prefixes'] = "|".join(exclude_prefixes)

            test_summary = f"querying {nameres_url_lookup} with label '{label}' and biolink_type {biolink_class}"
            if not test_row.PreferredID:
                pytest.xfail(f"Test {test_summary} cannot be tested without a preferred ID, skipping.")

            response = requests.get(nameres_url_lookup, params=request, timeout=NAMERES_TIMEOUT)
            count_tested_labels += 1

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

                continue

            # There are three possible responses:
            if not results:
                # 1. We got back no results.
                pytest.fail(f"No results for {test_summary} from {source_info}: {request}")
            elif expected_id == '':
                pytest.fail(f"No expected CURIE for {test_summary} from {source_info}: best result is {results[0]}")
            elif results[0]['curie'] == expected_id:
                top_result = results[0]
                assert top_result['curie'] == expected_id,\
                    f"{test_summary} returned expected ID {expected_id} as top result"

                # Test the preferred label if there is one.
                if test_row.PreferredLabel:
                    assert top_result['label'].lower() == test_row.PreferredLabel.lower(), f"{test_summary} returned preferred " + \
                        f"label {top_result['label']} instead of {test_row.PreferredLabel}."

                # Additionally, test the biolink_class_exclude field if there is one.
                if biolink_class_exclude:
                    assert biolink_class_exclude not in top_result['types'],\
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

    if count_tested_labels == 0:
        pytest.fail(f"No labels were tested for test row: {test_row}")
