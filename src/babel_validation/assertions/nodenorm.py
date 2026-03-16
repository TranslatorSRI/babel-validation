from typing import Iterator

from src.babel_validation.assertions import NodeNormTest
from src.babel_validation.core.testrow import TestResult
from src.babel_validation.services.nodenorm import CachedNodeNorm


class ResolvesHandler(NodeNormTest):
    """Test that every CURIE in every param_set resolves in NodeNorm."""
    NAME = "resolves"
    DESCRIPTION = "Each CURIE in each param_set must resolve to a non-null result in NodeNorm."
    PARAMETERS = "One or more CURIEs per param_set."
    WIKI_EXAMPLES = [
        "{{BabelTest|Resolves|CHEBI:15365}}",
        "{{BabelTest|Resolves|MONDO:0005015|DOID:9351}}",
    ]
    YAML_PARAMS = "    - CHEBI:15365\n    - [MONDO:0005015, DOID:9351]"

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
    DESCRIPTION = (
        "Each CURIE in each param_set must fail to resolve (return null) in NodeNorm. "
        "Use this to confirm that an identifier is intentionally not normalizable."
    )
    PARAMETERS = "One or more CURIEs per param_set."
    WIKI_EXAMPLES = ["{{BabelTest|DoesNotResolve|FAKENS:99999}}"]
    YAML_PARAMS = "    - FAKENS:99999"

    def test_param_set(self, params: list[str], nodenorm: CachedNodeNorm,
                       label: str = "") -> Iterator[TestResult]:
        for curie in params:
            result = nodenorm.normalize_curie(curie)
            if not result:
                yield self.passed(f"Could not resolve {curie} with NodeNormalization service {nodenorm} as expected")
            else:
                yield self.failed(f"Resolved {curie} to {result['id']['identifier']} ({result['type'][0]}, \"{result['id']['label']}\") with NodeNormalization service {nodenorm}, but expected not to resolve")


def _compare_resolutions(
    params: list[str], nodenorm: CachedNodeNorm
) -> tuple[dict | None, dict[str, dict | None]]:
    """Resolve all params; return (first_good_result, per_curie_results).

    first_good_result is None if every CURIE failed to resolve.
    per_curie_results maps each CURIE to its result (None if unresolvable).
    """
    per_curie = nodenorm.normalize_curies(params)
    first_good = next((r for r in per_curie.values() if r is not None), None)
    return first_good, per_curie


class ResolvesWithHandler(NodeNormTest):
    """Test that all CURIEs in a param_set resolve to the same normalized result in NodeNorm."""
    NAME = "resolveswith"
    DESCRIPTION = (
        "All CURIEs within each param_set must resolve to the identical normalized result. "
        "Use this to assert that two identifiers are equivalent."
    )
    PARAMETERS = "Two or more CURIEs per param_set. All must resolve to the same result."
    WIKI_EXAMPLES = ["{{BabelTest|ResolvesWith|CHEBI:15365|PUBCHEM.COMPOUND:1}}"]
    YAML_PARAMS = "    - [CHEBI:15365, PUBCHEM.COMPOUND:1]\n    - [MONDO:0005015, DOID:9351]"

    def test_param_set(self, params: list[str], nodenorm: CachedNodeNorm,
                       label: str = "") -> Iterator[TestResult]:
        first_good, results = _compare_resolutions(params, nodenorm)

        if first_good is None:
            yield self.failed(f"None of the CURIEs {params} could be resolved on {nodenorm}")
            return

        canonical_id = first_good['id']['identifier']

        for curie, result in results.items():
            if result is None:
                yield self.failed(
                    f"CURIE {curie} could not be resolved on {nodenorm}"
                )
            elif result['id']['identifier'] == canonical_id:
                yield self.passed(
                    f"Resolved {curie} to the expected canonical identifier {canonical_id}"
                )
            else:
                yield self.failed(
                    f"Resolved {curie} to {result['id']['identifier']} "
                    f"({result['type'][0]}, \"{result['id']['label']}\"), but expected "
                    f"{canonical_id} "
                    f"({first_good['type'][0]}, \"{first_good['id']['label']}\") on {nodenorm}"
                )


class DoesNotResolveWithHandler(NodeNormTest):
    """Test that not all CURIEs in a param_set resolve to the same result in NodeNorm."""
    NAME = "doesnotresolvewith"
    DESCRIPTION = (
        "The CURIEs within each param_set must NOT all resolve to the same normalized "
        "result. Use this to assert that two identifiers are intentionally distinct entities."
    )
    PARAMETERS = "Two or more CURIEs per param_set. They must not all resolve to the same result."
    WIKI_EXAMPLES = ["{{BabelTest|DoesNotResolveWith|CHEBI:15365|CHEBI:16856}}"]
    YAML_PARAMS = "    - [CHEBI:15365, CHEBI:16856]"

    def test_param_set(self, params: list[str], nodenorm: CachedNodeNorm,
                       label: str = "") -> Iterator[TestResult]:
        first_good, results = _compare_resolutions(params, nodenorm)

        # Every CURIE must resolve — an unresolved CURIE is a configuration error.
        unresolved = [curie for curie, result in results.items() if result is None]
        if unresolved:
            yield self.failed(
                f"CURIEs {unresolved} could not be resolved on {nodenorm}; "
                f"all CURIEs in a DoesNotResolveWith param_set must resolve"
            )
            return

        # All resolved — check that they don't all map to the same canonical identifier.
        canonical_ids = {result['id']['identifier'] for result in results.values()}

        if len(canonical_ids) == 1:
            # Every CURIE maps to the same result — assertion fails.
            shared = first_good
            yield self.failed(
                f"All CURIEs {params} resolved to the same result "
                f"{shared['id']['identifier']} "
                f"({shared['type'][0]}, \"{shared['id']['label']}\") on {nodenorm}, "
                f"but expected them to resolve differently"
            )
        else:
            summary = ", ".join(
                f"{curie} → {result['id']['identifier']}"
                for curie, result in results.items()
            )
            yield self.passed(
                f"CURIEs resolve to different results as expected: {summary} on {nodenorm}"
            )


class HasLabelHandler(NodeNormTest):
    """Test that a CURIE resolves to a specific primary label in NodeNorm."""
    NAME = "haslabel"

    def curie_params(self, params: list[str]) -> list[str]:
        return params[:1]
    DESCRIPTION = (
        "The CURIE must resolve in NodeNorm and its primary label (id.label) must "
        "match the expected label exactly (case-sensitive)."
    )
    PARAMETERS = "Exactly two elements per param_set: a CURIE, then the expected label string."
    WIKI_EXAMPLES = ["{{BabelTest|HasLabel|CHEBI:15365|aspirin}}"]
    YAML_PARAMS = "    - [CHEBI:15365, aspirin]"

    def test_param_set(self, params: list[str], nodenorm: CachedNodeNorm,
                       label: str = "") -> Iterator[TestResult]:
        # params[0] is the CURIE to resolve; params[1] is the expected label string.
        if len(params) < 2:
            yield self.failed(
                f"HasLabel requires two parameters (CURIE, expected label) in {label}, "
                f"but got: {params}"
            )
            return

        curie = params[0]
        expected_label = params[1].strip()

        result = nodenorm.normalize_curie(curie)
        if not result:
            yield self.failed(
                f"Could not resolve {curie} on {nodenorm}"
            )
            return

        actual_label = result['id']['label']
        if actual_label == expected_label:
            yield self.passed(
                f"CURIE {curie} has expected label '{actual_label}' on {nodenorm}"
            )
        else:
            yield self.failed(
                f"CURIE {curie} has label '{actual_label}', "
                f"but expected '{expected_label}' on {nodenorm}"
            )


class ResolvesWithTypeHandler(NodeNormTest):
    """Test that CURIEs resolve with a specific Biolink type in NodeNorm."""
    NAME = "resolveswithtype"

    def curie_params(self, params: list[str]) -> list[str]:
        return params[1:]
    DESCRIPTION = (
        "Each param_set must have at least two elements: the first is the expected Biolink type "
        "(e.g. 'biolink:Gene'), and the remainder are CURIEs that must resolve with that type."
    )
    PARAMETERS = (
        "Each param_set: first element is the expected Biolink type (e.g. `biolink:Gene`), "
        "remaining elements are CURIEs."
    )
    WIKI_EXAMPLES = ["{{BabelTest|ResolvesWithType|biolink:Gene|NCBIGene:1}}"]
    YAML_PARAMS = "    - [biolink:Gene, NCBIGene:1, HGNC:5]"

    def test_param_set(self, params: list[str], nodenorm: CachedNodeNorm,
                       label: str = "") -> Iterator[TestResult]:
        # params[0] is the expected Biolink type (e.g. "biolink:Gene");
        # params[1:] are the CURIEs that must resolve with that type.
        if len(params) < 2:
            yield self.failed(f"Too few parameters provided in param_set in {label}: {params}")
            return

        expected_biolink_type = params[0]
        curies = params[1:]

        results = nodenorm.normalize_curies(curies)
        for curie in curies:
            node = results.get(curie)
            if not node:
                yield self.failed(f"Could not resolve {curie} with NodeNormalization service {nodenorm}")
                continue
            biolink_types = node['type']
            if expected_biolink_type in biolink_types:
                yield self.passed(f"Biolink types {biolink_types} for CURIE {curie} includes expected Biolink type {expected_biolink_type}")
            else:
                yield self.failed(f"Biolink types {biolink_types} for CURIE {curie} does not include expected Biolink type {expected_biolink_type}")
