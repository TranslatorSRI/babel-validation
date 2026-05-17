import json
import logging
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
    PARAMETERS = (
        "Each param_set: the **search query string** and the **expected CURIE**. "
        "The CURIE is normalized via NodeNorm (drug/chemical conflation enabled) before matching."
    )
    WIKI_EXAMPLES = ["{{BabelTest|SearchByName|water|CHEBI:15377}}"]
    YAML_PARAMS = "    - [water, CHEBI:15377]\n    - [diabetes, MONDO:0005015]"

    def test_param_set(self, params: list[str], nodenorm: CachedNodeNorm,
                       nameres: CachedNameRes, pass_if_found_in_top: int = 5,
                       label: str = "") -> Iterator[TestResult]:
        if len(params) != 2:
            yield self.failed(
                f"SearchByName requires exactly two parameters (search query, expected CURIE) in {label}, "
                f"but got {len(params)}: {params}"
            )
            return

        [search_query, expected_curie_from_test] = params
        expected_curie_result = nodenorm.normalize_curie(expected_curie_from_test, drug_chemical_conflate='true')
        if not expected_curie_result:
            yield self.failed(f"Unable to normalize CURIE {expected_curie_from_test} in {label}")
            return

        expected_curie = expected_curie_result['id']['identifier']
        expected_curie_label = expected_curie_result['id']['label']
        expected_curie_string = f"Expected CURIE {expected_curie_from_test}, normalized to {expected_curie} '{expected_curie_label}'"

        results = nameres.lookup(search_query, autocomplete='false', limit=pass_if_found_in_top)
        if not results:
            yield self.failed(f"No results found for '{search_query}' on NameRes {nameres} ({expected_curie_string})")
            return

        curies = [result['curie'] for result in results]
        if expected_curie not in curies:
            logging.getLogger(__name__).debug(
                "%s not found in top %d results for '%s' in NameRes %s: %s",
                expected_curie_string, pass_if_found_in_top, search_query, nameres,
                json.dumps(results, indent=2, sort_keys=True)
            )
            yield self.failed(f"{expected_curie_string} not found in top {pass_if_found_in_top} results for '{search_query}' in NameRes {nameres}")
            return

        yield self.passed(f"{expected_curie_string} found at index {curies.index(expected_curie) + 1} on NameRes {nameres}")
