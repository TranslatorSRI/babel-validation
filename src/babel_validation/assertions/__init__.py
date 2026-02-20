"""
babel_validation.assertions
===========================

This package defines the assertion types that can be embedded in GitHub issue bodies
and evaluated against the NodeNorm and NameRes services.

Supported assertion types are registered in ASSERTION_HANDLERS. To see everything
that is currently supported, scan that dict or read assertions/README.md.

Adding a new assertion type
---------------------------
1. Create a subclass of NodeNormTest or NameResTest (or AssertionHandler for both)
   in the appropriate module (nodenorm.py, nameres.py, or common.py).
2. Set NAME and DESCRIPTION class attributes.
3. Override test_param_set().
4. Import it here and add an instance to ASSERTION_HANDLERS.
"""

from typing import Iterator

from src.babel_validation.core.testrow import TestResult, TestStatus


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
        """Evaluate this assertion against NodeNorm. Returns [] if not applicable."""
        return []

    def test_with_nameres(self, param_sets: list[list[str]], nodenorm, nameres,
                          pass_if_found_in_top: int = 5,
                          label: str = "") -> Iterator[TestResult]:
        """Evaluate this assertion against NameRes. Returns [] if not applicable."""
        return []


class NodeNormTest(AssertionHandler):
    """Base class for assertions that test NodeNorm.

    Subclasses implement test_param_set() instead of test_with_nodenorm().
    """

    def test_with_nodenorm(self, param_sets: list[list[str]], nodenorm,
                           label: str = "") -> Iterator[TestResult]:
        if not param_sets:
            yield self.failed(f"No parameters provided in {label}")
            return
        # warm the cache for all CURIEs up front
        nodenorm.normalize_curies([p for params in param_sets for p in params])
        found = False
        for index, params in enumerate(param_sets):
            if not params:
                yield self.failed(f"No parameters in param_set {index} in {label}")
                found = True
                continue
            for result in self.test_param_set(params, nodenorm, label):
                found = True
                yield result
        if not found:
            yield self.failed(f"No test results returned in {label}")

    def test_param_set(self, params: list[str], nodenorm, label: str = "") -> Iterator[TestResult]:
        """Override this to implement the assertion. Called once per param_set."""
        raise NotImplementedError

    def resolved_message(self, curie: str, result: dict, nodenorm) -> str:
        """Standard pass-message when a CURIE resolves."""
        return (f"Resolved {curie} to {result['id']['identifier']} "
                f"({result['type'][0]}, \"{result['id']['label']}\") "
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
        found = False
        for index, params in enumerate(param_sets):
            if not params:
                yield self.failed(f"No parameters in param_set {index} in {label}")
                found = True
                continue
            for result in self.test_param_set(params, nodenorm, nameres, pass_if_found_in_top, label):
                found = True
                yield result
        if not found:
            yield self.failed(f"No test results returned in {label}")

    def test_param_set(self, params: list[str], nodenorm, nameres,
                       pass_if_found_in_top: int, label: str = "") -> Iterator[TestResult]:
        """Override this to implement the assertion. Called once per param_set."""
        raise NotImplementedError


# Registry — import submodules after base classes are defined to avoid circular imports.
from src.babel_validation.assertions.nodenorm import (  # noqa: E402
    ResolvesHandler, DoesNotResolveHandler, ResolvesWithHandler, ResolvesWithTypeHandler,
)
from src.babel_validation.assertions.nameres import SearchByNameHandler  # noqa: E402
from src.babel_validation.assertions.common import NeededHandler  # noqa: E402

ASSERTION_HANDLERS: dict[str, AssertionHandler] = {
    h.NAME: h for h in [
        ResolvesHandler(),
        DoesNotResolveHandler(),
        ResolvesWithHandler(),
        ResolvesWithTypeHandler(),
        SearchByNameHandler(),
        NeededHandler(),
    ]
}
