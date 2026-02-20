import json
from typing import Iterator

from src.babel_validation.assertions import NodeNormTest
from src.babel_validation.core.testrow import TestResult
from src.babel_validation.services.nodenorm import CachedNodeNorm


class ResolvesHandler(NodeNormTest):
    """Test that every CURIE in every param_set resolves in NodeNorm."""
    NAME = "resolves"
    DESCRIPTION = "Each CURIE in each param_set must resolve to a non-null result in NodeNorm."

    def test_param_set(self, params: list[str], nodenorm: CachedNodeNorm,
                       label: str = "") -> Iterator[TestResult]:
        for curie in params:
            result = nodenorm.normalize_curie(curie)
            if not result:
                yield self.failed(f"Could not resolve {curie} with NodeNormalization service {nodenorm}")
            else:
                yield self.passed(self.resolved_message(curie, result, nodenorm))


class DoesNotResolveHandler(NodeNormTest):
    """Test that every CURIE in every param_set does NOT resolve in NodeNorm."""
    NAME = "doesnotresolve"
    DESCRIPTION = "Each CURIE in each param_set must fail to resolve (return null) in NodeNorm."

    def test_param_set(self, params: list[str], nodenorm: CachedNodeNorm,
                       label: str = "") -> Iterator[TestResult]:
        for curie in params:
            result = nodenorm.normalize_curie(curie)
            if not result:
                yield self.passed(f"Could not resolve {curie} with NodeNormalization service {nodenorm} as expected")
            else:
                yield self.failed(f"Resolved {curie} to {result['id']['identifier']} ({result['type'][0]}, \"{result['id']['label']}\") with NodeNormalization service {nodenorm}, but expected not to resolve")


class ResolvesWithHandler(NodeNormTest):
    """Test that all CURIEs in a param_set resolve to the same normalized result in NodeNorm."""
    NAME = "resolveswith"
    DESCRIPTION = (
        "All CURIEs within each param_set must resolve to the identical normalized result. "
        "Use this to assert that two identifiers are equivalent."
    )

    def test_param_set(self, params: list[str], nodenorm: CachedNodeNorm,
                       label: str = "") -> Iterator[TestResult]:
        results = nodenorm.normalize_curies(params)

        # Find the first good result.
        first_good_result = None
        for curie, result in results.items():
            if result is not None and first_good_result is None:
                first_good_result = result
                break

        if first_good_result is None:
            yield self.failed(f"None of the CURIEs {params} could be resolved on {nodenorm}")
            return

        # Check all the results.
        for curie, result in results.items():
            if result is None:
                yield self.failed(f"CURIE {curie} could not be resolved, and so is not equal to the expected result {json.dumps(first_good_result, indent=2, sort_keys=True)} on {nodenorm}")
            elif json.dumps(first_good_result, sort_keys=True) == json.dumps(result, sort_keys=True):
                yield self.passed(f"Resolved {curie} to the expected result {json.dumps(first_good_result, indent=2, sort_keys=True)}")
            else:
                yield self.failed(f"Resolved {curie} to {result['id']['identifier']} ({result['type'][0]}, \"{result['id']['label']}\"), but expected {first_good_result['id']['identifier']} ({first_good_result['type'][0]}, \"{first_good_result['id']['label']}\") on {nodenorm}")


class ResolvesWithTypeHandler(NodeNormTest):
    """Test that CURIEs resolve with a specific Biolink type in NodeNorm."""
    NAME = "resolveswithtype"
    DESCRIPTION = (
        "Each param_set must have at least two elements: the first is the expected Biolink type "
        "(e.g. 'biolink:Gene'), and the remainder are CURIEs that must resolve with that type."
    )

    def test_param_set(self, params: list[str], nodenorm: CachedNodeNorm,
                       label: str = "") -> Iterator[TestResult]:
        if len(params) < 2:
            yield self.failed(f"Too few parameters provided in param_set in {label}: {params}")
            return

        expected_biolink_type = params[0]
        curies = params[1:]

        results = nodenorm.normalize_curies(curies)
        for curie in curies:
            biolink_types = results[curie]['type']
            if expected_biolink_type in biolink_types:
                yield self.passed(f"Biolink types {biolink_types} for CURIE {curie} includes expected Biolink type {expected_biolink_type}")
            else:
                yield self.failed(f"Biolink types {biolink_types} for CURIE {curie} does not include expected Biolink type {expected_biolink_type}")
