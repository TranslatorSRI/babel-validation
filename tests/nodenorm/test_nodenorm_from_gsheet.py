import itertools
import urllib.parse
import requests
import pytest
from common.google_sheet_test_cases import GoogleSheetTestCases, TestRow

# We generate a set of tests from the GoogleSheetTestCases.
gsheet = GoogleSheetTestCases()


@pytest.mark.parametrize("test_row", gsheet.test_rows)
def test_normalization(target_info, test_row, test_category):
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