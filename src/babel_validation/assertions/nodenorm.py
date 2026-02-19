import json
from typing import Iterator

from src.babel_validation.assertions import NodeNormAssertion
from src.babel_validation.core.testrow import TestResult, TestStatus
from src.babel_validation.services.nodenorm import CachedNodeNorm


class ResolvesHandler(NodeNormAssertion):
    """Test that every CURIE in every param_set resolves in NodeNorm."""
    NAME = "resolves"
    DESCRIPTION = "Each CURIE in each param_set must resolve to a non-null result in NodeNorm."

    def test_with_nodenorm(self, param_sets: list[list[str]], nodenorm: CachedNodeNorm,
                           label: str = "") -> Iterator[TestResult]:
        if not param_sets:
            return [TestResult(status=TestStatus.Failed, message=f"No parameters provided in {label}")]

        curies_to_resolve = [param for params in param_sets for param in params]
        nodenorm.normalize_curies(curies_to_resolve)

        yielded_values = False
        for index, curies in enumerate(param_sets):
            if not curies:
                return TestResult(status=TestStatus.Failed, message=f"No parameters provided in paramset {index} in {label}")

            for curie in curies:
                result = nodenorm.normalize_curie(curie)
                if not result:
                    yield TestResult(status=TestStatus.Failed, message=f"Could not resolve {curie} with NodeNormalization service {nodenorm}")
                    yielded_values = True
                else:
                    yield TestResult(status=TestStatus.Passed, message=f"Resolved {curie} to {result['id']['identifier']} ({result['type'][0]}, \"{result['id']['label']}\") with NodeNormalization service {nodenorm}")
                    yielded_values = True

        if not yielded_values:
            return [TestResult(status=TestStatus.Failed, message=f"No test results returned in {label}")]


class DoesNotResolveHandler(NodeNormAssertion):
    """Test that every CURIE in every param_set does NOT resolve in NodeNorm."""
    NAME = "doesnotresolve"
    DESCRIPTION = "Each CURIE in each param_set must fail to resolve (return null) in NodeNorm."

    def test_with_nodenorm(self, param_sets: list[list[str]], nodenorm: CachedNodeNorm,
                           label: str = "") -> Iterator[TestResult]:
        if not param_sets:
            return [TestResult(status=TestStatus.Failed, message=f"No parameters provided in {label}")]

        curies_to_resolve = [param for params in param_sets for param in params]
        nodenorm.normalize_curies(curies_to_resolve)

        yielded_values = False
        for index, curies in enumerate(param_sets):
            if not curies:
                yield TestResult(status=TestStatus.Failed, message=f"No parameters provided in paramset {index} in {label}")
                continue

            for curie in curies:
                result = nodenorm.normalize_curie(curie)
                if not result:
                    yield TestResult(status=TestStatus.Passed, message=f"Could not resolve {curie} with NodeNormalization service {nodenorm} as expected")
                    yielded_values = True
                else:
                    yield TestResult(status=TestStatus.Failed, message=f"Resolved {curie} to {result['id']['identifier']} ({result['type'][0]}, \"{result['id']['label']}\") with NodeNormalization service {nodenorm}, but expected not to resolve")
                    yielded_values = True

        if not yielded_values:
            return [TestResult(status=TestStatus.Failed, message=f"No test results returned in {label}")]


class ResolvesWithHandler(NodeNormAssertion):
    """Test that all CURIEs in a param_set resolve to the same normalized result in NodeNorm."""
    NAME = "resolveswith"
    DESCRIPTION = (
        "All CURIEs within each param_set must resolve to the identical normalized result. "
        "Use this to assert that two identifiers are equivalent."
    )

    def test_with_nodenorm(self, param_sets: list[list[str]], nodenorm: CachedNodeNorm,
                           label: str = "") -> Iterator[TestResult]:
        if not param_sets:
            return [TestResult(status=TestStatus.Failed, message=f"No parameters provided in {label}")]

        curies_to_resolve = [param for params in param_sets for param in params]
        nodenorm.normalize_curies(curies_to_resolve)

        yielded_values = False
        for curies in param_sets:
            results = nodenorm.normalize_curies(curies)

            # Find the first good result.
            first_good_result = None
            for curie, result in results.items():
                if result is not None and first_good_result is None:
                    first_good_result = result
                    break

            if first_good_result is None:
                return [TestResult(status=TestStatus.Failed, message=f"None of the CURIEs {curies} could be resolved on {nodenorm}")]

            # Check all the results.
            for curie, result in results.items():
                if result is None:
                    yield TestResult(status=TestStatus.Failed, message=f"CURIE {curie} could not be resolved, and so is not equal to the expected result {json.dumps(first_good_result, indent=2, sort_keys=True)} on {nodenorm}")
                    yielded_values = True
                    continue

                if json.dumps(first_good_result, sort_keys=True) == json.dumps(result, sort_keys=True):
                    yield TestResult(status=TestStatus.Passed, message=f"Resolved {curie} to the expected result {json.dumps(first_good_result, indent=2, sort_keys=True)}")
                    yielded_values = True
                else:
                    yield TestResult(status=TestStatus.Failed, message=f"Resolved {curie} to {result['id']['identifier']} ({result['type'][0]}, \"{result['id']['label']}\"), but expected {first_good_result['id']['identifier']} ({first_good_result['type'][0]}, \"{first_good_result['id']['label']}\") on {nodenorm}")
                    yielded_values = True

        if not yielded_values:
            return [TestResult(status=TestStatus.Failed, message=f"No test results returned in {label}")]


class ResolvesWithTypeHandler(NodeNormAssertion):
    """Test that CURIEs resolve with a specific Biolink type in NodeNorm."""
    NAME = "resolveswithtype"
    DESCRIPTION = (
        "Each param_set must have at least two elements: the first is the expected Biolink type "
        "(e.g. 'biolink:Gene'), and the remainder are CURIEs that must resolve with that type."
    )

    def test_with_nodenorm(self, param_sets: list[list[str]], nodenorm: CachedNodeNorm,
                           label: str = "") -> Iterator[TestResult]:
        if not param_sets:
            return [TestResult(status=TestStatus.Failed, message=f"No parameters provided in {label}")]

        yielded_values = False
        for index, params in enumerate(param_sets):
            if len(params) < 2:
                yield TestResult(status=TestStatus.Failed, message=f"Too few parameters provided in param set {index} in {label}: {params}")
                continue

            expected_biolink_type = params[0]
            curies = params[1:]

            results = nodenorm.normalize_curies(curies)
            for curie in curies:
                biolink_types = results[curie]['type']
                if expected_biolink_type in biolink_types:
                    yield TestResult(status=TestStatus.Passed, message=f"Biolink types {biolink_types} for CURIE {curie} includes expected Biolink type {expected_biolink_type}")
                    yielded_values = True
                else:
                    yield TestResult(status=TestStatus.Failed, message=f"Biolink types {biolink_types} for CURIE {curie} does not include expected Biolink type {expected_biolink_type}")
                    yielded_values = True

        if not yielded_values:
            return [TestResult(status=TestStatus.Failed, message=f"No test results returned in {label}")]
