"""
babel_validation.assertions
===========================

This package defines the assertion types that can be embedded in GitHub issue bodies
and evaluated against the NodeNorm and NameRes services.

Supported assertion types are registered in ASSERTION_HANDLERS. To see everything
that is currently supported, scan that dict or read assertions/README.md.

**Adding a new assertion type: see the "Adding a New Assertion Type" section of
assertions/README.md.**  That section is generated from gen_docs.ADDING_NEW, and is
the one place those instructions live — a second copy here would drift out of step
with it, which is exactly what happened to the copy this note replaced.

The layout, for orientation while reading the code:

- AssertionHandler — the base class, and the strip/validate/warm machinery every
  assertion shares (prepare_params_lists).
- NodeNormTest / NameResTest — specialize it per service; subclasses override
  test_params_list() and are handed one params_list at a time.
- nodenorm.py, nameres.py, common.py — the concrete handlers.
- gen_docs.py — renders README.md from the handler classes.
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

# Small counts read better as words in a message ("exactly two parameters").
_COUNT_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


def _count(n: int) -> str:
    """"two" for small n, "17" for larger, plus the correctly pluralized noun."""
    return f"{_COUNT_WORDS.get(n, n)} parameter" + ("" if n == 1 else "s")


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

    # How many params a params_list must have. MAX_PARAMS None means no upper bound.
    # Checked during preparation: an assertion invoked with the wrong number of
    # params can never pass, so it is rejected before its CURIEs are looked up.
    MIN_PARAMS = 1
    MAX_PARAMS: int | None = None

    # Whether CURIE params should be rejected up front if they are not well-formed.
    # Assertions about deliberately-invalid identifiers turn this off.
    VALIDATE_CURIES = True

    _CURIE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9._-]*:[^\s]+$')

    # Params can come from an unreviewed GitHub issue body, so they are checked before reaching
    # a service. 1000 characters is far past any real CURIE (under 100) or Biolink type (under
    # 60) while still leaving room for a long chemical label — IUPAC names run well past 255 —
    # and keeps a NameRes query string well inside what proxies accept.
    MAX_PARAM_LENGTH = 1000

    def passed(self, message: str) -> TestResult:
        """Build a passing TestResult. Handlers use this rather than TestResult directly."""
        return TestResult(status=TestStatus.Passed, message=message)

    def failed(self, message: str) -> TestResult:
        """Build a failing TestResult. Handlers use this rather than TestResult directly."""
        return TestResult(status=TestStatus.Failed, message=message)

    @classmethod
    def display_name(cls) -> str:
        """The assertion name as written in issues (ResolvesHandler -> "Resolves").

        Derived from the class name rather than NAME, which is lowercased for
        case-insensitive matching and so reads poorly in a message or a heading.
        """
        return cls.__name__.removesuffix("Handler")

    @classmethod
    def _describe_arity(cls) -> str:
        """How many params this assertion takes, phrased for a failure message."""
        low, high = cls.MIN_PARAMS, cls.MAX_PARAMS
        if high is None:
            return f"at least {_count(low)}"
        if low == high:
            return f"exactly {_count(low)}"
        return f"between {_COUNT_WORDS.get(low, low)} and {_count(high)}"

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
        """Why *params* cannot be evaluated, or None if it can be.

        Ordered cheapest-first, and arity before CURIE validation, because
        curie_params() slices by position and only means anything once the
        params_list is known to be the right length.
        """
        if not params:
            return self.failed(f"No parameters in params_list {index} in {label}")
        # Before the arity and CURIE checks, because both interpolate params into their message.
        # This is also the only check that sees *every* param: _CURIE_RE skips the non-CURIE
        # params that curie_params() excludes — notably SearchByName's free-text query, the one
        # value that reaches a URL query string — and handlers with VALIDATE_CURIES = False skip
        # it entirely.
        for param in params:
            if not param:
                problem = "is empty"
            elif len(param) > self.MAX_PARAM_LENGTH:
                problem = f"is {len(param):,} characters, over the limit of {self.MAX_PARAM_LENGTH:,}"
            elif not param.isprintable():
                # isprintable() rejects ANSI escapes, C0/C1 controls, bidi overrides and
                # zero-width characters, all of which would otherwise be echoed to an operator's
                # terminal, into pytest IDs and into the logs.
                problem = "contains non-printable characters"
            else:
                continue
            # Truncate before repr()ing: the point of the length check is that this param may be
            # enormous, and this message is kept in pytest's report.
            shown = param[:100] + "..." if len(param) > 100 else param
            return self.failed(f"Parameter {shown!r} in params_list {index} in {label} {problem}")
        if len(params) < self.MIN_PARAMS or (
                self.MAX_PARAMS is not None and len(params) > self.MAX_PARAMS):
            return self.failed(
                f"{self.display_name()} requires {self._describe_arity()} "
                f"per params_list in {label}, but params_list {index} has "
                f"{len(params)}: {params}"
            )
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

        *params* already satisfies everything declared on the class: its length is
        within MIN_PARAMS/MAX_PARAMS, it is stripped, and (unless VALIDATE_CURIES
        is off) every param that curie_params() selects is a well-formed CURIE.
        Implementations may index into it accordingly without re-checking. Every
        CURIE is also pre-warmed in *nodenorm*'s cache, so normalize_curie() calls
        here are free.

        Yield one TestResult per thing checked — usually one per CURIE — rather
        than a single aggregate, so a failure report names the CURIE that failed.

        :param params: this params_list's parameters; see the handler's PARAMETERS.
        :param nodenorm: the NodeNorm service to evaluate against.
        :param label: human-readable identifier for the source being evaluated.
        """
        raise NotImplementedError

    # Stand-in for the Biolink type in a message when NodeNorm returned none.
    # Deliberately unlike any real type: current ones are prefixed ("biolink:Gene")
    # and older ones were lowercase prose ("chemical entity"), so shouting it in
    # caps keeps a reader from mistaking the placeholder for a type Babel returned.
    NO_TYPE = 'NO TYPE RETURNED'

    @staticmethod
    def first_type(result: dict) -> str:
        """First Biolink type of a resolved node, or NO_TYPE if the node has none.

        NodeNorm normally returns a non-empty `type` list, but guard against an empty
        (or missing) one so message formatting never raises IndexError/KeyError."""
        types = result.get('type') or []
        return types[0] if types else NodeNormTest.NO_TYPE

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

        *params* satisfies MIN_PARAMS/MAX_PARAMS and is stripped, with the params
        that curie_params() selects validated as CURIEs and pre-warmed in
        *nodenorm*'s cache. See NodeNormTest.test_params_list() for the shared
        contract; the arguments are documented on test_with_nameres().
        """
        raise NotImplementedError


# Registry — import submodules after base classes are defined to avoid circular imports.
from src.babel_validation.assertions.nodenorm import (  # noqa: E402
    ResolvesHandler, DoesNotResolveHandler, ResolvesWithHandler,
    ResolvesWithTypeHandler, DoesNotResolveWithHandler, HasLabelHandler,
)
from src.babel_validation.assertions.nameres import (  # noqa: E402
    SearchByNameHandler, SearchByNameTopResultHandler, DoesNotSearchByNameHandler,
)
from src.babel_validation.assertions.common import NeededHandler  # noqa: E402

def _register(handlers: list[AssertionHandler]) -> dict[str, AssertionHandler]:
    """Index *handlers* by NAME, rejecting what a dict comprehension would hide.

    Assertion names are matched case-insensitively by lowercasing the name used
    in the issue, so a NAME that is not already lowercase can never be looked up.
    A duplicate NAME would silently drop one of the two handlers.  Both are
    mistakes only made while adding an assertion, so fail loudly at import.
    """
    registry: dict[str, AssertionHandler] = {}
    for handler in handlers:
        name = handler.NAME
        if not name or name != name.lower():
            raise ValueError(
                f"{type(handler).__name__}.NAME must be a non-empty lowercase string, got {name!r}"
            )
        if name in registry:
            raise ValueError(
                f"{type(handler).__name__}.NAME {name!r} is already registered "
                f"by {type(registry[name]).__name__}"
            )
        registry[name] = handler
    return registry


# Every assertion type the parser will recognise, keyed by its lowercase NAME.
# Registration order is irrelevant — README.md groups handlers by the service they
# test, not by their position here.
ASSERTION_HANDLERS: dict[str, AssertionHandler] = _register([
    ResolvesHandler(),
    DoesNotResolveHandler(),
    ResolvesWithHandler(),
    DoesNotResolveWithHandler(),
    HasLabelHandler(),
    ResolvesWithTypeHandler(),
    SearchByNameHandler(),
    SearchByNameTopResultHandler(),
    DoesNotSearchByNameHandler(),
    NeededHandler(),
])
