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
6. Run `uv run python -m babel_validation.assertions.gen_docs` to regenerate README.md.
"""

import re
from typing import Iterator

from babel_validation.core.testrow import TestResult, TestStatus


class AssertionHandler:
    """Base class for all BabelTest assertion handlers."""
    NAME: str           # lowercase assertion name as used in issue bodies
    DESCRIPTION: str    # one-line human-readable description

    def passed(self, message: str) -> TestResult:
        return TestResult(status=TestStatus.Passed, message=message)

    def failed(self, message: str) -> TestResult:
        return TestResult(status=TestStatus.Failed, message=message)

    def test_with_nodenorm(self, param_sets: list[list[str]], nodenorm,
                           label: str = "") -> Iterator[TestResult]:
        """Evaluate this assertion against NodeNorm. Returns [] if not applicable.

        :param param_sets: list[list[str]] — see github_issues_test_cases.py module
                           docstring for the full definition of param_set / param_sets.
        """
        return []

    def test_with_nameres(self, param_sets: list[list[str]], nodenorm, nameres,
                          pass_if_found_in_top: int = 5,
                          label: str = "") -> Iterator[TestResult]:
        """Evaluate this assertion against NameRes. Returns [] if not applicable.

        :param param_sets: list[list[str]] — see github_issues_test_cases.py module
                           docstring for the full definition of param_set / param_sets.
        """
        return []


class NodeNormTest(AssertionHandler):
    """Base class for assertions that test NodeNorm.

    Subclasses implement test_param_set() instead of test_with_nodenorm().
    """

    _CURIE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9._-]*:[^\s]+$')

    def curie_params(self, params: list[str]) -> list[str]:
        """Return the subset of params that are CURIEs (for prewarming and validation).
        Default: all params are CURIEs. Subclasses override when some params are non-CURIEs."""
        return params

    def test_with_nodenorm(self, param_sets: list[list[str]], nodenorm,
                           label: str = "") -> Iterator[TestResult]:
        if not param_sets:
            yield self.failed(f"No parameters provided in {label}")
            return
        # Validate each param_set up front so malformed CURIEs are never sent to
        # NodeNorm — not even in the cache-warming call below.
        failures: dict[int, TestResult] = {}
        for index, params in enumerate(param_sets):
            if not params:
                failures[index] = self.failed(f"No parameters in param_set {index} in {label}")
                continue
            invalid = [c for c in self.curie_params(params) if not self._CURIE_RE.match(c)]
            if invalid:
                failures[index] = self.failed(
                    f"Malformed CURIE(s) {invalid} in param_set {index} in {label}: "
                    f"expected format PREFIX:LOCAL_ID (e.g. CHEBI:15365)"
                )
        # warm the cache only for params that are CURIEs (deduplicated); skip if empty
        # (normalize_curies raises ValueError on an empty list)
        curies_to_warm = list({
            p
            for index, params in enumerate(param_sets)
            if index not in failures
            for p in self.curie_params(params)
        })
        if curies_to_warm:
            nodenorm.normalize_curies(curies_to_warm)
        results = []
        for index, params in enumerate(param_sets):
            if index in failures:
                results.append(failures[index])
                continue
            results.extend(self.test_param_set(params, nodenorm, label))
        if not results:
            yield self.failed(f"No test results returned in {label}")
            return
        yield from results

    def test_param_set(self, params: list[str], nodenorm, label: str = "") -> Iterator[TestResult]:
        """Override this to implement the assertion. Called once per param_set.

        :param params: A single param_set — one element of the outer param_sets list.
                       See github_issues_test_cases.py for the full terminology.
        """
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

    def test_with_nameres(self, param_sets: list[list[str]], nodenorm, nameres,
                          pass_if_found_in_top: int = 5,
                          label: str = "") -> Iterator[TestResult]:
        if not param_sets:
            yield self.failed(f"No parameters provided in {label}")
            return
        results = []
        for index, params in enumerate(param_sets):
            if not params:
                results.append(self.failed(f"No parameters in param_set {index} in {label}"))
                continue
            results.extend(self.test_param_set(params, nodenorm, nameres, pass_if_found_in_top, label))
        if not results:
            yield self.failed(f"No test results returned in {label}")
            return
        yield from results

    def test_param_set(self, params: list[str], nodenorm, nameres,
                       pass_if_found_in_top: int, label: str = "") -> Iterator[TestResult]:
        """Override this to implement the assertion. Called once per param_set.

        :param params: A single param_set — one element of the outer param_sets list.
                       See github_issues_test_cases.py for the full terminology.
        """
        raise NotImplementedError


# Registry — import submodules after base classes are defined to avoid circular imports.
from babel_validation.assertions.nodenorm import (  # noqa: E402
    ResolvesHandler, DoesNotResolveHandler, ResolvesWithHandler,
    ResolvesWithTypeHandler, DoesNotResolveWithHandler, HasLabelHandler,
)
from babel_validation.assertions.nameres import SearchByNameHandler  # noqa: E402
from babel_validation.assertions.common import NeededHandler  # noqa: E402

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
