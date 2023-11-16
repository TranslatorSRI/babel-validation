import urllib.parse
import requests
import pytest
from common.google_sheet_test_cases import GoogleSheetTestCases, TestRow

# We generate a set of tests from the GoogleSheetTestCases.
gsheet = GoogleSheetTestCases()


@pytest.mark.parametrize("test_row", gsheet.test_rows)
def test_label(target_info, test_row, test_category):
    nameres_url = target_info['NameResURL']
    limit = target_info['NameResLimit']

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
    query_labels = [test_row.QueryLabel]
    query_labels.extend(test_row.AdditionalLabels)

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

            assert response.ok, f"Could not send request {request} to GET {nameres_url_lookup}: {response}"
            results = response.json()

            # All curies
            all_curies = list(map(lambda r: r['curie'], results))

            # Check for negative results
            if 'negative' in test_row.Flags:
                if not results:
                    assert not results, f"Negative test {test_summary} successful: no results found."
                    continue

                top_result = results[0]
                if top_result['label'] == label:
                    pytest.fail(f"Negative test {test_summary} found top result with label '{label}': {results}")
                else:
                    pytest.xfail(f"Negative test {test_summary} found results, but top result doesn't have label '{label}': {results}")

            # There are three possible responses:
            if not results:
                # 1. We got back no results.
                pytest.fail(f"No results for {test_summary} from {source_info}")
            elif expected_id == '':
                pytest.fail(f"No expected CURIE for {test_summary} from {source_info}: best result is {results[0]}")
            elif results[0]['curie'] == expected_id:
                top_result = results[0]
                assert top_result['curie'] == expected_id,\
                    f"{test_summary} returned expected ID {expected_id} as top result"

                # Additionally, test the biolink_class_exclude field if there is one.
                if biolink_class_exclude:
                    assert biolink_class_exclude not in top_result['types'],\
                        f"Biolink types for {top_result['curie']} are {top_result['types']}, which includes {biolink_class_exclude} which should be excluded."

            elif expected_id in all_curies:
                expected_index = all_curies.index(expected_id)
                pytest.fail(f"{test_summary} returns {results[0]['curie']} ('{results[0]['label']}') as the "
                            f"top result, but {expected_id} is at {expected_index} index.")
            else:
                pytest.fail(f"{test_summary} but expected result {expected_id} not found: {results}")
