"""Offline regression tests for assertion/service handling of sparse NodeNorm responses.

NodeNorm may omit `label` or `type` from a node, and may omit a requested CURIE
from its response entirely. Each of these used to raise KeyError or silently pass.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.babel_validation.assertions.nameres import SearchByNameHandler
from src.babel_validation.assertions.nodenorm import (
    DoesNotResolveWithHandler,
    ResolvesWithHandler,
    ResolvesWithTypeHandler,
)
from src.babel_validation.core.testrow import TestStatus
from src.babel_validation.services.nodenorm import CachedNodeNorm

pytestmark = pytest.mark.unit

UNLABELLED = {"id": {"identifier": "UMLS:C0000001"}}


def _nodenorm(mapping):
    """A CachedNodeNorm whose normalize_curies/normalize_curie serve `mapping`."""
    nodenorm = MagicMock(spec=CachedNodeNorm)
    nodenorm.normalize_curies.side_effect = lambda curies, **kw: {c: mapping.get(c) for c in curies}
    nodenorm.normalize_curie.side_effect = lambda curie, **kw: mapping.get(curie)
    return nodenorm


def test_search_by_name_survives_node_without_label():
    nameres = MagicMock()
    nameres.lookup.return_value = [{"curie": "UMLS:C0000001"}]
    results = list(SearchByNameHandler().test_param_set(
        ["something", "UMLS:C0000001"], _nodenorm({"UMLS:C0000001": UNLABELLED}), nameres))
    assert [r.status for r in results] == [TestStatus.Passed]


def test_resolves_with_type_survives_node_without_type():
    results = list(ResolvesWithTypeHandler().test_param_set(
        ["biolink:Gene", "UMLS:C0000001"], _nodenorm({"UMLS:C0000001": UNLABELLED})))
    assert [r.status for r in results] == [TestStatus.Failed]
    assert "biolink:Gene" in results[0].message


def test_resolves_with_expectation_follows_param_order_not_dict_order():
    """The 'but expected X' in the message must not depend on cache/set ordering."""
    mapping = {
        "AAA:1": {"id": {"identifier": "AAA:1"}},
        "BBB:2": {"id": {"identifier": "AAA:1"}},
        "CCC:3": {"id": {"identifier": "CCC:3"}},
    }
    nodenorm = MagicMock(spec=CachedNodeNorm)
    # Return the CURIEs in an order unrelated to the param_set order.
    nodenorm.normalize_curies.side_effect = lambda curies, **kw: {
        c: mapping[c] for c in reversed(list(curies))
    }
    results = list(ResolvesWithHandler().test_param_set(["AAA:1", "BBB:2", "CCC:3"], nodenorm))
    failures = [r for r in results if r.status == TestStatus.Failed]
    assert len(failures) == 1
    assert "but expected AAA:1" in failures[0].message


def test_normalize_curies_returns_an_entry_for_every_requested_curie():
    """A CURIE omitted by NodeNorm must still appear (as None), or assertions that
    iterate the result — e.g. DoesNotResolveWith — pass vacuously."""
    nodenorm = CachedNodeNorm("http://example.invalid/")
    response = MagicMock()
    response.json.return_value = {"AAA:1": {"id": {"identifier": "AAA:1"}}}  # BBB:2 omitted
    with patch("src.babel_validation.services.nodenorm.requests.post", return_value=response):
        result = nodenorm.normalize_curies(["AAA:1", "BBB:2"])
    assert result == {"AAA:1": {"id": {"identifier": "AAA:1"}}, "BBB:2": None}

    # ...and the assertion built on it does not pass vacuously.
    results = list(DoesNotResolveWithHandler().test_param_set(
        ["AAA:1", "BBB:2"], _nodenorm({"AAA:1": None, "BBB:2": None})))
    assert all(r.status == TestStatus.Failed for r in results)
