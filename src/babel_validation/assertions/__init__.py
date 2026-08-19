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
4. Override test_params_list().
5. Import it here and add an instance to ASSERTION_HANDLERS.
6. Run `uv run python -m src.babel_validation.assertions.gen_docs` to regenerate README.md.
"""

import re
from dataclasses import dataclass
from typing import Iterator

from src.babel_validation.core.testrow import TestResult, TestStatus
from src.babel_validation.services.nameres import NameResService
from src.babel_validation.services.nodenorm import NodeNormService

# The parameters of a single assertion invocation, e.g. ["CHEBI:15365", "aspirin"]
# for {{BabelTest|HasLabel|CHEBI:15365|aspirin}}. What each element means depends
# on the assertion, and position is significant: ResolvesWithType takes its
# Biolink type first, HasLabel is [curie, label]. See the handler's PARAMETERS.
ParamsList = list[str]


@dataclass(frozen=True)
class PreparedParamsList:
    """One params_list after stripping and validation, ready to be evaluated.

    *failure* is None when the params_list is usable. When it is set, the
    params_list was rejected before reaching the service and *failure* is the
    TestResult to report in its place.
    """
    params: ParamsList
    failure: TestResult | None = None


class AssertionHandler:
    """Base class for all BabelTest assertion handlers.

    A handler is a stateless singleton: one instance per assertion type lives in
    ASSERTION_HANDLERS and is shared by every issue being evaluated. Do not store
    per-evaluation state on ``self``.

    Every handler declares the five documentation attributes below; gen_docs.py
    renders README.md from them, so they are part of the handler's contract
    rather than optional commentary.
    """

    NAME: str                  # lowercase assertion name as used in issue bodies
    DESCRIPTION: str           # one-line human-readable description
    PARAMETERS: str            # markdown describing what each param means
    WIKI_EXAMPLES: list[str]   # complete {{BabelTest|...}} lines, shown verbatim
    YAML_PARAMS: str           # indented YAML list entries for the babel_tests example

    # Whether CURIE params should be rejected up front if they are not well-formed.
    # Assertions about deliberately-invalid identifiers turn this off.
    VALIDATE_CURIES = True

    _CURIE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9._-]*:[^\s]+$')

    def passed(self, message: str) -> TestResult:
        """Build a passing TestResult. Handlers use this rather than TestResult directly."""
        return TestResult(status=TestStatus.Passed, message=message)

    def failed(self, message: str) -> TestResult:
        """Build a failing TestResult. Handlers use this rather than TestResult directly."""
        return TestResult(status=TestStatus.Failed, message=message)

    def curie_params(self, params: ParamsList) -> ParamsList:
        """Return the subset of params that are CURIEs (for prewarming and validation).
        Default: all params are CURIEs. Subclasses override when some params are non-CURIEs."""
        return params

    def prepare_params_lists(self, params_lists: list[ParamsList],
                             nodenorm: NodeNormService,
                             label: str = "") -> list[PreparedParamsList]:
        """Strip params, reject unusable params_lists, and warm the NodeNorm cache.

        :param params_lists: the params_lists to prepare, as parsed from the issue.
        :param nodenorm: service whose cache is warmed with every CURIE about to be
            looked up, so the per-params_list evaluation costs no further HTTP calls.
        :param label: human-readable identifier for the source being evaluated (an
            issue number, a test name); appears in failure messages so a reader can
            tell which assertion produced them.
        :returns: one PreparedParamsList per input params_list, in order, each either
            carrying stripped params or a failure explaining why it was rejected.

        Rejected params_lists are excluded from cache warming, so (unless
        VALIDATE_CURIES is off) malformed CURIEs are never sent to NodeNorm.
        """
        prepared = []
        for index, params in enumerate(params_lists):
            stripped = [param.strip() for param in params]
            prepared.append(PreparedParamsList(stripped, self._rejection(index, stripped, label)))

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

    def _rejection(self, index: int, params: ParamsList, label: str) -> TestResult | None:
        """Why *params* cannot be evaluated, or None if it can be."""
        if not params:
            return self.failed(f"No parameters in params_list {index} in {label}")
        if not self.VALIDATE_CURIES:
            return None
        invalid = [c for c in self.curie_params(params) if not self._CURIE_RE.match(c)]
        if invalid:
            return self.failed(
                f"Malformed CURIE(s) {invalid} in params_list {index} in {label}: "
                f"expected format PREFIX:LOCAL_ID (e.g. CHEBI:15365)"
            )
        return None

    def test_with_nodenorm(self, params_lists: list[ParamsList],
                           nodenorm: NodeNormService,
                           label: str = "") -> Iterator[TestResult]:
        """Evaluate this assertion against NodeNorm, yielding one TestResult per check.

        The base implementation yields nothing, which is how an assertion declares
        it has no NodeNorm meaning: a caller runs every handler against both
        services and an empty iterator simply contributes no results.

        :param params_lists: every params_list this assertion was invoked with; each
            is evaluated independently, so one bad params_list does not sink the rest.
        :param nodenorm: the NodeNorm service to evaluate against. Typically a
            CachedNodeNorm for a specific deployment (dev, prod, ...), which is what
            makes the same assertion runnable against several environments.
        :param label: human-readable identifier for the source being evaluated; see
            prepare_params_lists().
        """
        return iter([])

    def test_with_nameres(self, params_lists: list[ParamsList],
                          nodenorm: NodeNormService, nameres: NameResService,
                          pass_if_found_in_top: int = 5,
                          label: str = "") -> Iterator[TestResult]:
        """Evaluate this assertion against NameRes, yielding one TestResult per check.

        As with test_with_nodenorm(), yielding nothing means "not applicable".

        NameRes assertions get *both* services: NameRes answers the lookup, and
        NodeNorm normalizes the expected CURIE so that a lookup result can be
        compared against it by canonical identifier rather than by exact string.

        :param params_lists: every params_list this assertion was invoked with.
        :param nodenorm: used to normalize expected CURIEs before comparison.
        :param nameres: the NameRes service to evaluate against.
        :param pass_if_found_in_top: how far down the ranked results the expected
            CURIE may appear and still count as a pass. Also caps the number of
            results requested from NameRes.
        :param label: human-readable identifier for the source being evaluated.
        """
        return iter([])


class NodeNormTest(AssertionHandler):
    """Base class for assertions that test NodeNorm.

    Subclasses implement test_params_list() instead of test_with_nodenorm().
    """

    def test_with_nodenorm(self, params_lists: list[ParamsList],
                           nodenorm: NodeNormService,
                           label: str = "") -> Iterator[TestResult]:
        if not params_lists:
            yield self.failed(f"No parameters provided in {label}")
            return
        results = []
        for prepared in self.prepare_params_lists(params_lists, nodenorm, label):
            if prepared.failure:
                results.append(prepared.failure)
                continue
            results.extend(self.test_params_list(prepared.params, nodenorm, label))
        if not results:
            yield self.failed(f"No test results returned in {label}")
            return
        yield from results

    def test_params_list(self, params: ParamsList, nodenorm: NodeNormService,
                         label: str = "") -> Iterator[TestResult]:
        """Override this to implement the assertion. Called once per params_list.

        *params* is non-empty and already stripped, and (unless VALIDATE_CURIES is
        off) every param that curie_params() selects is a well-formed CURIE, so
        implementations need only check assertion-specific shape such as arity.
        Every CURIE is also pre-warmed in *nodenorm*'s cache, so normalize_curie()
        calls here are free.

        Yield one TestResult per thing checked — usually one per CURIE — rather
        than a single aggregate, so a failure report names the CURIE that failed.

        :param params: this params_list's parameters; see the handler's PARAMETERS.
        :param nodenorm: the NodeNorm service to evaluate against.
        :param label: human-readable identifier for the source being evaluated.
        """
        raise NotImplementedError

    @staticmethod
    def first_type(result: dict) -> str:
        """First Biolink type of a resolved node, or a placeholder if the node has none.

        NodeNorm normally returns a non-empty `type` list, but guard against an empty
        (or missing) one so message formatting never raises IndexError/KeyError."""
        types = result.get('type') or []
        return types[0] if types else 'unknown type'

    def resolved_message(self, curie: str, result: dict,
                         nodenorm: NodeNormService) -> str:
        """Standard pass-message when a CURIE resolves.

        *result* is one entry of a NodeNorm get_normalized_nodes response, i.e. a
        non-None value from normalize_curie()/normalize_curies().
        """
        return (f"Resolved {curie} to {result['id']['identifier']} "
                f"({self.first_type(result)}, \"{result['id'].get('label', '')}\") "
                f"with NodeNormalization service {nodenorm}")


class NameResTest(AssertionHandler):
    """Base class for assertions that test NameRes.

    Subclasses implement test_params_list() instead of test_with_nameres().
    """

    def test_with_nameres(self, params_lists: list[ParamsList],
                          nodenorm: NodeNormService, nameres: NameResService,
                          pass_if_found_in_top: int = 5,
                          label: str = "") -> Iterator[TestResult]:
        if not params_lists:
            yield self.failed(f"No parameters provided in {label}")
            return
        results = []
        for prepared in self.prepare_params_lists(params_lists, nodenorm, label):
            if prepared.failure:
                results.append(prepared.failure)
                continue
            results.extend(
                self.test_params_list(prepared.params, nodenorm, nameres, pass_if_found_in_top, label))
        if not results:
            yield self.failed(f"No test results returned in {label}")
            return
        yield from results

    def test_params_list(self, params: ParamsList, nodenorm: NodeNormService,
                         nameres: NameResService, pass_if_found_in_top: int,
                         label: str = "") -> Iterator[TestResult]:
        """Override this to implement the assertion. Called once per params_list.

        *params* is non-empty and already stripped, with the params that
        curie_params() selects validated as CURIEs and pre-warmed in *nodenorm*'s
        cache. See NodeNormTest.test_params_list() for the shared contract; the
        arguments are documented on test_with_nameres().
        """
        raise NotImplementedError


# Registry — import submodules after base classes are defined to avoid circular imports.
from src.babel_validation.assertions.nodenorm import (  # noqa: E402
    ResolvesHandler, DoesNotResolveHandler, ResolvesWithHandler,
    ResolvesWithTypeHandler, DoesNotResolveWithHandler, HasLabelHandler,
)
from src.babel_validation.assertions.nameres import SearchByNameHandler  # noqa: E402
from src.babel_validation.assertions.common import NeededHandler  # noqa: E402

# Every assertion type the parser will recognise, keyed by its lowercase NAME.
# Registration order is irrelevant — README.md groups handlers by the service they
# test, not by their position here.
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
