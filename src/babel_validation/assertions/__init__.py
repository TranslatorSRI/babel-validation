"""
babel_validation.assertions
===========================

This package defines the assertion types that can be embedded in GitHub issue bodies
and evaluated against the NodeNorm and NameRes services.

Supported assertion types are registered in ASSERTION_HANDLERS. To see everything
that is currently supported, scan that dict or read assertions/README.md (auto-generated).

Adding a new assertion type
---------------------------
1. Create a subclass of NodeNormTest or NameResTest (or AssertionHandler for both)
   in the appropriate module (nodenorm.py, nameres.py, or common.py).
2. Set NAME and DESCRIPTION class attributes.
3. Set PARAMETERS, WIKI_EXAMPLES, and YAML_PARAMS class attributes for documentation.
4. Override test_param_set().
5. Import it here and add an instance to ASSERTION_HANDLERS.
6. Run `uv run python -m src.babel_validation.assertions.gen_docs` to regenerate README.md.
"""

import re
from dataclasses import dataclass
from typing import Iterator

from src.babel_validation.core.testrow import TestResult, TestStatus

# The parameters of a single assertion invocation, e.g. ["CHEBI:15365", "aspirin"]
# for {{BabelTest|HasLabel|CHEBI:15365|aspirin}}. What each element means depends
# on the assertion; see the handler's PARAMETERS attribute.
Params = list[str]

# The param_sets of one assertion: each is evaluated independently, and each
# produces its own TestResults.
ParamSets = list[Params]


@dataclass(frozen=True)
class PreparedParamSet:
    """One param_set after stripping and validation, ready to be evaluated.

    *failure* is None when the param_set is usable. When it is set, the
    param_set was rejected before reaching the service and *failure* is the
    TestResult to report in its place.
    """
    params: Params
    failure: TestResult | None = None


class AssertionHandler:
    """Base class for all BabelTest assertion handlers."""
    NAME: str           # lowercase assertion name as used in issue bodies
    DESCRIPTION: str    # one-line human-readable description

    # Whether CURIE params should be rejected up front if they are not well-formed.
    # Assertions about deliberately-invalid identifiers turn this off.
    VALIDATE_CURIES = True

    _CURIE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9._-]*:[^\s]+$')

    def passed(self, message: str) -> TestResult:
        return TestResult(status=TestStatus.Passed, message=message)

    def failed(self, message: str) -> TestResult:
        return TestResult(status=TestStatus.Failed, message=message)

    def curie_params(self, params: Params) -> Params:
        """Return the subset of params that are CURIEs (for prewarming and validation).
        Default: all params are CURIEs. Subclasses override when some params are non-CURIEs."""
        return params

    def prepare_param_sets(self, param_sets: ParamSets, nodenorm,
                           label: str = "") -> list[PreparedParamSet]:
        """Strip params, reject unusable param_sets, and warm the NodeNorm cache.

        Returns one PreparedParamSet per input param_set, in order, each either
        carrying stripped params or a failure explaining why it was rejected.
        Rejected param_sets are excluded from cache warming, so (unless
        VALIDATE_CURIES is off) malformed CURIEs are never sent to NodeNorm.
        """
        prepared = []
        for index, params in enumerate(param_sets):
            stripped = [param.strip() for param in params]
            prepared.append(PreparedParamSet(stripped, self._rejection(index, stripped, label)))

        # Warm the cache in a single request, deduplicated; skip if empty
        # (normalize_curies raises ValueError on an empty list).
        curies_to_warm = list({
            curie
            for p in prepared if p.failure is None
            for curie in self.curie_params(p.params)
        })
        if curies_to_warm:
            nodenorm.normalize_curies(curies_to_warm)

        return prepared

    def _rejection(self, index: int, params: Params, label: str) -> TestResult | None:
        """Why *params* cannot be evaluated, or None if it can be."""
        if not params:
            return self.failed(f"No parameters in param_set {index} in {label}")
        if not self.VALIDATE_CURIES:
            return None
        invalid = [c for c in self.curie_params(params) if not self._CURIE_RE.match(c)]
        if invalid:
            return self.failed(
                f"Malformed CURIE(s) {invalid} in param_set {index} in {label}: "
                f"expected format PREFIX:LOCAL_ID (e.g. CHEBI:15365)"
            )
        return None

    def test_with_nodenorm(self, param_sets: ParamSets, nodenorm,
                           label: str = "") -> Iterator[TestResult]:
        """Evaluate this assertion against NodeNorm. Returns nothing if not applicable."""
        return iter([])

    def test_with_nameres(self, param_sets: ParamSets, nodenorm, nameres,
                          pass_if_found_in_top: int = 5,
                          label: str = "") -> Iterator[TestResult]:
        """Evaluate this assertion against NameRes. Returns nothing if not applicable."""
        return iter([])


class NodeNormTest(AssertionHandler):
    """Base class for assertions that test NodeNorm.

    Subclasses implement test_param_set() instead of test_with_nodenorm().
    """

    def test_with_nodenorm(self, param_sets: ParamSets, nodenorm,
                           label: str = "") -> Iterator[TestResult]:
        if not param_sets:
            yield self.failed(f"No parameters provided in {label}")
            return
        results = []
        for prepared in self.prepare_param_sets(param_sets, nodenorm, label):
            if prepared.failure:
                results.append(prepared.failure)
                continue
            results.extend(self.test_param_set(prepared.params, nodenorm, label))
        if not results:
            yield self.failed(f"No test results returned in {label}")
            return
        yield from results

    def test_param_set(self, params: Params, nodenorm, label: str = "") -> Iterator[TestResult]:
        """Override this to implement the assertion. Called once per param_set."""
        raise NotImplementedError

    @staticmethod
    def first_type(result: dict) -> str:
        """First Biolink type of a resolved node, or a placeholder if the node has none.

        NodeNorm normally returns a non-empty `type` list, but guard against an empty
        (or missing) one so message formatting never raises IndexError/KeyError."""
        types = result.get('type') or []
        return types[0] if types else 'unknown type'

    def resolved_message(self, curie: str, result: dict, nodenorm) -> str:
        """Standard pass-message when a CURIE resolves."""
        return (f"Resolved {curie} to {result['id']['identifier']} "
                f"({self.first_type(result)}, \"{result['id'].get('label', '')}\") "
                f"with NodeNormalization service {nodenorm}")


class NameResTest(AssertionHandler):
    """Base class for assertions that test NameRes.

    Subclasses implement test_param_set() instead of test_with_nameres().
    """

    def test_with_nameres(self, param_sets: ParamSets, nodenorm, nameres,
                          pass_if_found_in_top: int = 5,
                          label: str = "") -> Iterator[TestResult]:
        if not param_sets:
            yield self.failed(f"No parameters provided in {label}")
            return
        results = []
        for prepared in self.prepare_param_sets(param_sets, nodenorm, label):
            if prepared.failure:
                results.append(prepared.failure)
                continue
            results.extend(
                self.test_param_set(prepared.params, nodenorm, nameres, pass_if_found_in_top, label))
        if not results:
            yield self.failed(f"No test results returned in {label}")
            return
        yield from results

    def test_param_set(self, params: Params, nodenorm, nameres,
                       pass_if_found_in_top: int, label: str = "") -> Iterator[TestResult]:
        """Override this to implement the assertion. Called once per param_set."""
        raise NotImplementedError


# Registry — import submodules after base classes are defined to avoid circular imports.
from src.babel_validation.assertions.nodenorm import (  # noqa: E402
    ResolvesHandler, DoesNotResolveHandler, ResolvesWithHandler,
    ResolvesWithTypeHandler, DoesNotResolveWithHandler, HasLabelHandler,
)
from src.babel_validation.assertions.nameres import SearchByNameHandler  # noqa: E402
from src.babel_validation.assertions.common import NeededHandler  # noqa: E402

ASSERTION_HANDLERS: dict[str, AssertionHandler] = {
    h.NAME: h for h in [
        ResolvesHandler(),
        DoesNotResolveHandler(),
        ResolvesWithHandler(),
        DoesNotResolveWithHandler(),
        HasLabelHandler(),
        ResolvesWithTypeHandler(),
        SearchByNameHandler(),
        NeededHandler(),
    ]
}
