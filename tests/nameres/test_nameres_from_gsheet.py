import urllib.parse
import requests
import pytest
from common.google_sheet_test_cases import GoogleSheetTestCases, TestRow

# We generate a set of tests from the GoogleSheetTestCases.
gsheet = GoogleSheetTestCases()


@pytest.mark.parametrize("test_row", gsheet.test_rows)
def test_label(target_info, test_row):
    nameres_url = target_info['NameResURL']

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
    for label in query_labels:
        for biolink_class in biolink_classes:
            nameres_url_lookup = urllib.parse.urljoin(nameres_url, 'lookup')
            request = {
                "string": label,
                "biolink_type": biolink_class,
                "limit": 100
            }
            test_summary = f"querying {nameres_url_lookup} with label {label} and biolink_type {biolink_class}"
            response = requests.get(nameres_url_lookup, request)

            assert response.ok, f"Could not send request {request} to GET {nameres_url_lookup}: {response}"
            results = response.json()

            # All curies
            all_curies = [map(lambda r: r['curie'], results)]

            # There are three possible responses:
            if not results:
                # 1. We got back no results.
                pytest.fail(f"No results for {test_summary} from {source_info}")
            elif expected_id == '':
                pytest.fail(f"No expected CURIE for {test_summary} from {source_info}: best result is {results[0]}")
            elif results[0]['curie'] == expected_id:
                assert results[0]['curie'] == expected_id, f"{test_summary} returned expected ID {expected_id} as first result"
            elif expected_id in all_curies:
                expected_index = all_curies.index(all_curies)
                pytest.fail(f"{test_summary} returns {results[0]['curie']} ('{results[0]['label']}') as the "
                            f"top result, but {expected_id} is at {expected_index} index.")
            else:
                if 'negative' in test_row.Flags:
                    pytest.fail(f"Negative test {test_summary} found expected result {expected_id} not found: {results}")
                else:
                    pytest.fail(f"{test_summary} but expected result {expected_id} not found: {results}")