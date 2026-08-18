"""Unit tests for the assertion handlers, with NodeNorm's HTTP layer stubbed out.

These run against the real CachedNodeNorm so that the bulk-normalization contract
(one entry per requested CURIE) is exercised, not just re-stated by a fake.
"""

import pytest

from src.babel_validation.assertions import ASSERTION_HANDLERS, NodeNormTest
from src.babel_validation.assertions.gen_docs import generate_readme
from src.babel_validation.assertions.nodenorm import (
    DoesNotResolveHandler, DoesNotResolveWithHandler, ResolvesHandler, ResolvesWithHandler,
)
from src.babel_validation.core.testrow import TestStatus
from src.babel_validation.services import nodenorm as nodenorm_service


def _node(identifier, label):
    return {'id': {'identifier': identifier, 'label': label}, 'type': ['biolink:SmallMolecule']}


# A:1 and B:1 are equivalent; C:1 is a distinct entity; D:1 is dropped from the
# response entirely, which is what NodeNorm does for some unknown identifiers.
FAKE_NODENORM_DB = {
    'A:1': _node('A:1', 'alpha'),
    'B:1': _node('A:1', 'alpha'),
    'C:1': _node('C:1', 'gamma'),
}


@pytest.fixture
def nodenorm(monkeypatch):
    """A CachedNodeNorm backed by FAKE_NODENORM_DB, with a .post_count attribute."""
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._payload

    def fake_post(url, json=None, timeout=None):
        calls.append(json['curies'])
        return FakeResponse({c: FAKE_NODENORM_DB[c] for c in json['curies'] if c in FAKE_NODENORM_DB})

    monkeypatch.setattr(nodenorm_service.requests, 'post', fake_post)
    service = nodenorm_service.CachedNodeNorm('http://fake-nodenorm.example/')
    service.post_calls = calls
    return service


def _messages(results):
    return [(r.status, r.message) for r in results]


@pytest.mark.unit
def test_normalize_curies_covers_every_requested_curie(nodenorm):
    """NodeNorm omitting a CURIE must surface as None, not as a missing key."""
    results = nodenorm.normalize_curies(['A:1', 'D:1'])
    assert list(results) == ['A:1', 'D:1']
    assert results['D:1'] is None


@pytest.mark.unit
def test_resolves_with_fails_on_omitted_curie(nodenorm):
    results = list(ResolvesWithHandler().test_with_nodenorm([['A:1', 'D:1']], nodenorm, 'test'))
    failures = [m for status, m in _messages(results) if status == TestStatus.Failed]
    assert any('D:1' in m for m in failures), _messages(results)


@pytest.mark.unit
def test_does_not_resolve_with_fails_on_omitted_curie(nodenorm):
    """The 'every CURIE must resolve' guard must see the dropped CURIE."""
    results = list(DoesNotResolveWithHandler().test_with_nodenorm([['A:1', 'C:1', 'D:1']], nodenorm, 'test'))
    assert all(status == TestStatus.Failed for status, _ in _messages(results)), _messages(results)
    assert any('D:1' in m for _, m in _messages(results))


@pytest.mark.unit
def test_resolves_with_blames_the_odd_curie_out(nodenorm):
    """The canonical identifier comes from the first param, so C:1 is the failure."""
    results = list(ResolvesWithHandler().test_with_nodenorm([['A:1', 'B:1', 'C:1']], nodenorm, 'test'))
    failures = [m for status, m in _messages(results) if status == TestStatus.Failed]
    assert len(failures) == 1 and failures[0].startswith('Resolved C:1'), _messages(results)


@pytest.mark.unit
def test_does_not_resolve_accepts_a_malformed_identifier(nodenorm):
    """A junk identifier is exactly what DoesNotResolve exists to assert about."""
    results = list(DoesNotResolveHandler().test_with_nodenorm([['not a curie']], nodenorm, 'test'))
    assert [status for status, _ in _messages(results)] == [TestStatus.Passed], _messages(results)


@pytest.mark.unit
def test_surrounding_whitespace_is_stripped(nodenorm):
    results = list(ResolvesHandler().test_with_nodenorm([['  A:1  ']], nodenorm, 'test'))
    assert [status for status, _ in _messages(results)] == [TestStatus.Passed], _messages(results)


@pytest.mark.unit
def test_search_by_name_validates_and_warms_before_calling_nodenorm(nodenorm):
    """The NameRes path gets the same CURIE validation as the NodeNorm path."""
    handler = ASSERTION_HANDLERS['searchbyname']
    results = list(handler.test_with_nameres([['water', 'not a curie']], nodenorm, None, 5, 'test'))
    assert [status for status, _ in _messages(results)] == [TestStatus.Failed], _messages(results)
    assert nodenorm.post_calls == []


class TempGroupingHandler(NodeNormTest):
    """Registered last, after the NameRes handlers, only by test_docs_group_handlers_*."""
    NAME = 'tempgrouping'
    DESCRIPTION = 'Temporary handler used to check README grouping.'
    PARAMETERS = ''
    WIKI_EXAMPLES = ['{{BabelTest|TempGrouping|A:1}}']
    YAML_PARAMS = '    - A:1'


@pytest.mark.unit
def test_docs_group_handlers_by_service_not_registration_order():
    """A NodeNorm handler registered last must still render under NodeNorm."""
    ASSERTION_HANDLERS[TempGroupingHandler.NAME] = TempGroupingHandler()
    try:
        readme = generate_readme()
    finally:
        del ASSERTION_HANDLERS[TempGroupingHandler.NAME]
    assert '### TempGrouping' in readme
    assert readme.index('### TempGrouping') < readme.index('## NameRes Assertions')
