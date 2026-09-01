import json
import logging
from typing import Iterator

from src.babel_validation.assertions import NameResTest, ParamsList
from src.babel_validation.core.testrow import TestResult
from src.babel_validation.services.nameres import NameResService
from src.babel_validation.services.nodenorm import NodeNormService


class SearchByNameHandler(NameResTest):
    """Test that a name search returns an expected CURIE in the top-N results in NameRes."""
    NAME = "searchbyname"
    DESCRIPTION = (
        "Each params_list must have exactly two elements: a search query string and an expected CURIE. "
        "The test passes if the CURIE's normalized identifier appears within the top N results "
        "(default N=5) when NameRes looks up the search query."
    )
    PARAMETERS = (
        "Each params_list: the **search query string** and the **expected CURIE**. "
        "The CURIE is normalized via NodeNorm before matching."
    )
    WIKI_EXAMPLES = ["{{BabelTest|SearchByName|water|CHEBI:15377}}"]
    YAML_PARAMS = "    - [water, CHEBI:15377]\n    - [diabetes, MONDO:0005015]"

    MIN_PARAMS = MAX_PARAMS = 2  # [search query, expected CURIE]

    def curie_params(self, params: ParamsList) -> ParamsList:
        # params[0] is a free-text search query; only the expected CURIE is a CURIE.
        return params[1:2]

    def test_params_list(self, params: ParamsList, nodenorm: NodeNormService,
                         nameres: NameResService, pass_if_found_in_top: int = 5,
                         label: str = "") -> Iterator[TestResult]:
        [search_query, expected_curie_from_test] = params
        expected_curie_result = nodenorm.normalize_curie(expected_curie_from_test)
        if not expected_curie_result:
            yield self.failed(f"Unable to normalize CURIE {expected_curie_from_test} in {label}")
            return

        expected_curie = expected_curie_result['id']['identifier']
        expected_curie_label = expected_curie_result['id'].get('label', '')
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


class SearchByNameTopResultHandler(NameResTest):
    """Test that a name search returns an expected CURIE as the *first* result in NameRes."""
    NAME = "searchbynametopresult"
    DESCRIPTION = (
        "Each params_list must have exactly two elements: a search query string and an expected CURIE. "
        "The test passes only if the CURIE's normalized identifier is the very first result when "
        "NameRes looks up the search query. Use this rather than SearchByName when the point is that "
        "the concept must win, not merely appear: SearchByName accepts anything in the top N."
    )
    PARAMETERS = (
        "Each params_list: the **search query string** and the **expected CURIE**. "
        "The CURIE is normalized via NodeNorm before matching."
    )
    WIKI_EXAMPLES = ["{{BabelTest|SearchByNameTopResult|water|CHEBI:15377}}"]
    YAML_PARAMS = "    - [water, CHEBI:15377]\n    - [diabetes, MONDO:0005015]"

    MIN_PARAMS = MAX_PARAMS = 2  # [search query, expected CURIE]

    def curie_params(self, params: ParamsList) -> ParamsList:
        # params[0] is a free-text search query; only the expected CURIE is a CURIE.
        return params[1:2]

    def test_params_list(self, params: ParamsList, nodenorm: NodeNormService,
                         nameres: NameResService, pass_if_found_in_top: int = 5,
                         label: str = "") -> Iterator[TestResult]:
        [search_query, expected_curie_from_test] = params
        expected_curie_result = nodenorm.normalize_curie(expected_curie_from_test)
        if not expected_curie_result:
            yield self.failed(f"Unable to normalize CURIE {expected_curie_from_test!r} in {label}")
            return

        expected_curie = expected_curie_result['id']['identifier']
        expected_curie_label = expected_curie_result['id'].get('label', '')
        expected_curie_string = (
            f"Expected CURIE {expected_curie_from_test!r}, normalized to "
            f"{expected_curie!r} {expected_curie_label!r}"
        )

        # Ask for the top N rather than just the top 1, so a failure can say how far
        # down the expected CURIE actually landed. "at rank 4" tells you it is a
        # ranking problem; "not in the top 5" tells you it is a retrieval one.
        results = nameres.lookup(search_query, autocomplete='false', limit=pass_if_found_in_top)
        if not results:
            yield self.failed(
                f"No results found for {search_query!r} on NameRes {nameres} ({expected_curie_string})")
            return

        curies = [result['curie'] for result in results]
        if curies[0] == expected_curie:
            yield self.passed(
                f"{expected_curie_string} is the top result for {search_query!r} on NameRes {nameres}")
            return

        top = results[0]
        if expected_curie in curies:
            yield self.failed(
                f"{expected_curie_string} is at rank {curies.index(expected_curie) + 1} for "
                f"{search_query!r} on NameRes {nameres}, behind {top['curie']!r} "
                f"{top.get('label', '')!r}"
            )
        else:
            yield self.failed(
                f"{expected_curie_string} is not in the top {pass_if_found_in_top} results for "
                f"{search_query!r} on NameRes {nameres}; the top result is {top['curie']!r} "
                f"{top.get('label', '')!r}"
            )


class DoesNotSearchByNameHandler(NameResTest):
    """Test that a name search does *not* return a CURIE in the top-N results in NameRes."""
    NAME = "doesnotsearchbyname"
    DESCRIPTION = (
        "Each params_list must have exactly two elements: a search query string and a CURIE that "
        "must not be returned. The test passes if the CURIE's normalized identifier is absent from "
        "the top N results (default N=5) when NameRes looks up the search query. This is how a "
        "blocklisted term is asserted: the term is searchable, but the concept must not come back."
    )
    PARAMETERS = (
        "Each params_list: the **search query string** and the **CURIE that must not be returned**. "
        "The CURIE is normalized via NodeNorm before matching."
    )
    WIKI_EXAMPLES = ["{{BabelTest|DoesNotSearchByName|mongoloid|HP:0000582}}"]
    YAML_PARAMS = "    - [mongoloid, HP:0000582]\n    - [retard, HP:0006887]"

    MIN_PARAMS = MAX_PARAMS = 2  # [search query, CURIE that must not be returned]

    def curie_params(self, params: ParamsList) -> ParamsList:
        # params[0] is a free-text search query; only the rejected CURIE is a CURIE.
        return params[1:2]

    def test_params_list(self, params: ParamsList, nodenorm: NodeNormService,
                         nameres: NameResService, pass_if_found_in_top: int = 5,
                         label: str = "") -> Iterator[TestResult]:
        [search_query, rejected_curie_from_test] = params

        # A CURIE that will not normalize is a failure here, not a pass, even though
        # "we could not look it up" and "it was not returned" both end with the CURIE
        # absent from the results. A typo in a negative assertion would otherwise
        # succeed forever while testing nothing, which is the one way a blocklist test
        # can be worse than no test at all. DoesNotResolve takes the opposite line
        # (VALIDATE_CURIES = False) because there the CURIE failing to resolve *is*
        # the thing being asserted.
        rejected_curie_result = nodenorm.normalize_curie(rejected_curie_from_test)
        if not rejected_curie_result:
            yield self.failed(f"Unable to normalize CURIE {rejected_curie_from_test!r} in {label}")
            return

        rejected_curie = rejected_curie_result['id']['identifier']
        rejected_curie_label = rejected_curie_result['id'].get('label', '')
        rejected_curie_string = (
            f"Rejected CURIE {rejected_curie_from_test!r}, normalized to "
            f"{rejected_curie!r} {rejected_curie_label!r}"
        )

        results = nameres.lookup(search_query, autocomplete='false', limit=pass_if_found_in_top)
        curies = [result['curie'] for result in results]
        if rejected_curie not in curies:
            yield self.passed(
                f"{rejected_curie_string} is absent from the top {pass_if_found_in_top} results "
                f"for {search_query!r} on NameRes {nameres}")
            return

        index = curies.index(rejected_curie)
        logging.getLogger(__name__).debug(
            "%s was returned at rank %d for '%s' in NameRes %s: %s",
            rejected_curie_string, index + 1, search_query, nameres,
            json.dumps(results, indent=2, sort_keys=True)
        )
        yield self.failed(
            f"{rejected_curie_string} was returned at rank {index + 1} for {search_query!r} "
            f"on NameRes {nameres}: {results[index].get('label', '')!r}"
        )
