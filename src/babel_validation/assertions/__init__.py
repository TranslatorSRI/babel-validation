"""
babel_validation.assertions
===========================

This package defines the assertion types that can be embedded in GitHub issue bodies
and evaluated against the NodeNorm and NameRes services.

Supported assertion types are registered in ASSERTION_HANDLERS. To see everything
that is currently supported, scan that dict or read assertions/README.md.

Adding a new assertion type
---------------------------
1. Create a subclass of AssertionHandler (or NodeNormAssertion / NameResAssertion)
   in the appropriate module (nodenorm.py, nameres.py, or common.py).
2. Set NAME and DESCRIPTION class attributes.
3. Override test_with_nodenorm() and/or test_with_nameres().
4. Import it here and add an instance to ASSERTION_HANDLERS.
"""

from typing import Iterator

from src.babel_validation.core.testrow import TestResult


class AssertionHandler:
    """Base class for all BabelTest assertion handlers."""
    NAME: str           # lowercase assertion name as used in issue bodies
    DESCRIPTION: str    # one-line human-readable description

    def test_with_nodenorm(self, param_sets: list[list[str]], nodenorm,
                           label: str = "") -> Iterator[TestResult]:
        """Evaluate this assertion against NodeNorm. Returns [] if not applicable."""
        return []

    def test_with_nameres(self, param_sets: list[list[str]], nodenorm, nameres,
                          pass_if_found_in_top: int = 5,
                          label: str = "") -> Iterator[TestResult]:
        """Evaluate this assertion against NameRes. Returns [] if not applicable."""
        return []


class NodeNormAssertion(AssertionHandler):
    """Marker base class for assertions that test NodeNorm.

    Subclasses must override test_with_nodenorm().
    test_with_nameres() returns [] and need not be overridden.
    Use isinstance(handler, NodeNormAssertion) to check applicability.
    """
    pass


class NameResAssertion(AssertionHandler):
    """Marker base class for assertions that test NameRes.

    Subclasses must override test_with_nameres().
    test_with_nodenorm() returns [] and need not be overridden.
    Use isinstance(handler, NameResAssertion) to check applicability.
    """
    pass


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
