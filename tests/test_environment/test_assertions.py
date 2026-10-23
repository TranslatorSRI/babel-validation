"""Unit tests for the assertion handlers, with NodeNorm's HTTP layer stubbed out.

These run against the real CachedNodeNorm so that the bulk-normalization contract
(one entry per requested CURIE) is exercised, not just re-stated by a fake.
"""

import pytest

from src.babel_validation.assertions import ASSERTION_HANDLERS, NodeNormTest, _register
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


class FakeNameRes:
    """Returns a fixed result list, whatever it is asked. str() reaches the messages."""

    def __init__(self, curies):
        self._results = [{'curie': c, 'label': f'label for {c}'} for c in curies]

    def lookup(self, query, **params):
        return self._results

    def __str__(self):
        return 'FakeNameRes'


@pytest.mark.unit
@pytest.mark.parametrize('returned,expected_status,expected_in_message', [
    (['A:1', 'C:1'], TestStatus.Passed, 'is the top result'),
    (['C:1', 'A:1'], TestStatus.Failed, 'is at rank 2'),
    (['C:1'], TestStatus.Failed, 'is not in the top 5'),
    ([], TestStatus.Failed, 'No results found'),
])
def test_search_by_name_top_result_only_accepts_rank_one(
        nodenorm, returned, expected_status, expected_in_message):
    """SearchByName accepts anything in the top N; this one must not.

    The two failure messages are deliberately different: "at rank 2" is a ranking
    problem, "not in the top 5" is a retrieval one, and they have different owners.
    """
    handler = ASSERTION_HANDLERS['searchbynametopresult']
    results = list(handler.test_with_nameres(
        [['water', 'B:1']], nodenorm, FakeNameRes(returned), 5, 'test'))
    [(status, message)] = _messages(results)
    assert status == expected_status, message
    assert expected_in_message in message


@pytest.mark.unit
@pytest.mark.parametrize('returned,expected_status,expected_in_message', [
    (['C:1'], TestStatus.Passed, 'is absent from the top 5'),
    ([], TestStatus.Passed, 'is absent from the top 5'),
    (['A:1'], TestStatus.Failed, 'was returned at rank 1'),
    (['C:1', 'A:1'], TestStatus.Failed, 'was returned at rank 2'),
])
def test_does_not_search_by_name(nodenorm, returned, expected_status, expected_in_message):
    """B:1 normalizes to A:1, so the assertion is about the clique, not the string."""
    handler = ASSERTION_HANDLERS['doesnotsearchbyname']
    results = list(handler.test_with_nameres(
        [['mongoloid', 'B:1']], nodenorm, FakeNameRes(returned), 5, 'test'))
    [(status, message)] = _messages(results)
    assert status == expected_status, message
    assert expected_in_message in message


@pytest.mark.unit
def test_does_not_search_by_name_fails_on_a_curie_it_cannot_normalize(nodenorm):
    """The one way a negative assertion can be worse than no assertion.

    D:1 is dropped from the NodeNorm response entirely. "We could not look it up" and
    "it was not returned" both end with the CURIE absent from the results, so treating
    the first as a pass would let a typo'd blocklist assertion succeed forever while
    testing nothing.
    """
    handler = ASSERTION_HANDLERS['doesnotsearchbyname']
    results = list(handler.test_with_nameres(
        [['mongoloid', 'D:1']], nodenorm, FakeNameRes([]), 5, 'test'))
    [(status, message)] = _messages(results)
    assert status == TestStatus.Failed, message
    assert 'Unable to normalize' in message


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


@pytest.mark.unit
def test_missing_biolink_type_placeholder_cannot_pass_for_a_real_type():
    """Nodes do carry types normally, but the stand-in must not read as one of them."""
    assert NodeNormTest.first_type({'type': ['biolink:Gene']}) == 'biolink:Gene'
    for typeless in ({}, {'type': []}, {'type': None}):
        placeholder = NodeNormTest.first_type(typeless)
        assert placeholder == NodeNormTest.NO_TYPE
        # Unlike a current type (biolink:Gene) or a legacy one (chemical entity).
        assert not placeholder.startswith('biolink:')
        assert placeholder.isupper()


@pytest.mark.unit
def test_registration_rejects_names_that_could_never_be_matched():
    """Assertion lookup lowercases the issue's name, so an uppercase NAME is unreachable."""
    class UppercaseHandler(TempGroupingHandler):
        NAME = 'Resolves'

    with pytest.raises(ValueError, match='lowercase'):
        _register([UppercaseHandler()])


@pytest.mark.unit
def test_registration_rejects_a_duplicate_name():
    """A dict comprehension would silently drop one of the two handlers."""
    with pytest.raises(ValueError, match='already registered'):
        _register([TempGroupingHandler(), TempGroupingHandler()])


@pytest.mark.unit
def test_registered_handlers_satisfy_those_rules():
    assert all(name == name.lower() for name in ASSERTION_HANDLERS)
    assert len(ASSERTION_HANDLERS) == 10


@pytest.mark.unit
@pytest.mark.parametrize('handler_name,params', [
    ('searchbyname', ['water', 'CHEBI:15377', 'unexpected']),  # exactly two
    ('haslabel', ['CHEBI:15365']),                             # exactly two
    ('resolveswith', ['A:1']),                                 # at least two
    ('resolveswithtype', ['biolink:Gene']),                    # at least two
])
def test_wrong_arity_is_rejected_without_calling_nodenorm(nodenorm, handler_name, params):
    """A params_list that can never pass must not cost a NodeNorm lookup first."""
    handler = ASSERTION_HANDLERS[handler_name]
    if handler_name == 'searchbyname':
        results = list(handler.test_with_nameres([params], nodenorm, None, 5, 'test'))
    else:
        results = list(handler.test_with_nodenorm([params], nodenorm, 'test'))

    assert [status for status, _ in _messages(results)] == [TestStatus.Failed], _messages(results)
    assert handler.display_name() in results[0].message
    assert nodenorm.post_calls == [], 'rejected params_list should not have been looked up'


@pytest.mark.unit
def test_a_good_params_list_still_gets_warmed(nodenorm):
    """The arity guard must not stop legitimate params_lists from being pre-warmed."""
    list(ASSERTION_HANDLERS['resolveswith'].test_with_nodenorm([['A:1', 'B:1']], nodenorm, 'test'))
    assert nodenorm.post_calls == [['A:1', 'B:1']] or nodenorm.post_calls == [['B:1', 'A:1']]
