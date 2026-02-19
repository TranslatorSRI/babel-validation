import json
from typing import Iterator

from src.babel_validation.assertions import NameResAssertion
from src.babel_validation.core.testrow import TestResult, TestStatus
from src.babel_validation.services.nameres import CachedNameRes
from src.babel_validation.services.nodenorm import CachedNodeNorm


class SearchByNameHandler(NameResAssertion):
    """Test that a name search returns an expected CURIE in the top-N results in NameRes."""
    NAME = "searchbyname"
    DESCRIPTION = (
        "Each param_set must have at least two elements: a search query string and an expected CURIE. "
        "The test passes if the CURIE's normalized identifier appears within the top N results "
        "(default N=5) when NameRes looks up the search query."
    )

    def test_with_nameres(self, param_sets: list[list[str]], nodenorm: CachedNodeNorm,
                          nameres: CachedNameRes, pass_if_found_in_top: int = 5,
                          label: str = "") -> Iterator[TestResult]:
        if not param_sets:
            return [TestResult(status=TestStatus.Failed, message=f"No parameters provided in {label}")]

        yielded_values = False
        for params in param_sets:
            if len(params) < 2:
                yield TestResult(status=TestStatus.Failed, message=f"Two parameters expected for SearchByName in {label}, but params = {params}")
                yielded_values = True
                continue

            [search_query, expected_curie_from_test, *args] = params
            expected_curie_result = nodenorm.normalize_curie(expected_curie_from_test, drug_chemical_conflate='true')
            if not expected_curie_result:
                yield TestResult(status=TestStatus.Failed, message=f"Unable to normalize CURIE {expected_curie_from_test} in {label}")
                yielded_values = True
                continue

            expected_curie = expected_curie_result['id']['identifier']
            expected_curie_label = expected_curie_result['id']['label']
            expected_curie_string = f"Expected CURIE {expected_curie_from_test}, normalized to {expected_curie} '{expected_curie_label}'"

            # Search for the expected CURIE in the first {pass_if_found_in_top} results.
            results = nameres.lookup(search_query, autocomplete='false', limit=(2 * pass_if_found_in_top))
            if not results:
                yield TestResult(status=TestStatus.Failed, message=f"No results found for '{search_query}' on NameRes {nameres} ({expected_curie_string}")
                yielded_values = True
                continue

            curies = [result['curie'] for result in results]
            try:
                found_index = curies.index(expected_curie)
            except ValueError:
                yield TestResult(status=TestStatus.Failed, message=f"{expected_curie_string} not found when searching for '{search_query}' in NameRes {nameres}: {json.dumps(results, indent=2, sort_keys=True)}")
                yielded_values = True
                continue

            if found_index <= pass_if_found_in_top:
                yield TestResult(status=TestStatus.Passed, message=f"{expected_curie_string} found at index {found_index + 1} on NameRes {nameres}")
            else:
                yield TestResult(status=TestStatus.Failed, message=f"{expected_curie_string} found at index {found_index + 1} which is greater than {pass_if_found_in_top} on NameRes {nameres}")
            yielded_values = True

        if not yielded_values:
            return [TestResult(status=TestStatus.Failed, message=f"No test results returned in {label}")]
