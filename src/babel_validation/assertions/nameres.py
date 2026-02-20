import json
from typing import Iterator

from src.babel_validation.assertions import NameResTest
from src.babel_validation.core.testrow import TestResult
from src.babel_validation.services.nameres import CachedNameRes
from src.babel_validation.services.nodenorm import CachedNodeNorm


class SearchByNameHandler(NameResTest):
    """Test that a name search returns an expected CURIE in the top-N results in NameRes."""
    NAME = "searchbyname"
    DESCRIPTION = (
        "Each param_set must have at least two elements: a search query string and an expected CURIE. "
        "The test passes if the CURIE's normalized identifier appears within the top N results "
        "(default N=5) when NameRes looks up the search query."
    )

    def test_param_set(self, params: list[str], nodenorm: CachedNodeNorm,
                       nameres: CachedNameRes, pass_if_found_in_top: int = 5,
                       label: str = "") -> Iterator[TestResult]:
        if len(params) < 2:
            yield self.failed(f"Two parameters expected for SearchByName in {label}, but params = {params}")
            return

        [search_query, expected_curie_from_test, *args] = params
        expected_curie_result = nodenorm.normalize_curie(expected_curie_from_test, drug_chemical_conflate='true')
        if not expected_curie_result:
            yield self.failed(f"Unable to normalize CURIE {expected_curie_from_test} in {label}")
            return

        expected_curie = expected_curie_result['id']['identifier']
        expected_curie_label = expected_curie_result['id']['label']
        expected_curie_string = f"Expected CURIE {expected_curie_from_test}, normalized to {expected_curie} '{expected_curie_label}'"

        # Search for the expected CURIE in the first {pass_if_found_in_top} results.
        results = nameres.lookup(search_query, autocomplete='false', limit=(2 * pass_if_found_in_top))
        if not results:
            yield self.failed(f"No results found for '{search_query}' on NameRes {nameres} ({expected_curie_string}")
            return

        curies = [result['curie'] for result in results]
        try:
            found_index = curies.index(expected_curie)
        except ValueError:
            yield self.failed(f"{expected_curie_string} not found when searching for '{search_query}' in NameRes {nameres}: {json.dumps(results, indent=2, sort_keys=True)}")
            return

        if found_index <= pass_if_found_in_top:
            yield self.passed(f"{expected_curie_string} found at index {found_index + 1} on NameRes {nameres}")
        else:
            yield self.failed(f"{expected_curie_string} found at index {found_index + 1} which is greater than {pass_if_found_in_top} on NameRes {nameres}")
