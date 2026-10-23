#
# Tests for NameRes exact mode: the `exact` parameter that NameRes v1.7.1 added to /lookup and
# /bulk-lookup (https://github.com/NCATSTranslator/NameResolution/releases/tag/v1.7.1).
#
# `exact=label` matches the whole preferred name, `exact=synonyms` a whole synonym, and `exact=any`
# either, case-insensitively and after leading and trailing whitespace is stripped. These tests
# check that each mode finds what it should, that the searches the tokenized search matches by
# fragment, word order or punctuation no longer match, and that exact mode composes with the other
# parameters. Every test is skipped on a deployment older than v1.7.1, which would otherwise
# silently ignore `exact` (see require_nameres_version()).
#
# The expected CURIEs were checked against Babel 2026jul22 on NameRes v1.7.1; a later Babel
# release that renames one of these concepts will need this table updated.
#
import urllib.parse

import pytest
import requests

from src.babel_validation.services.nameres import CachedNameRes
from tests._nameres_exact import EXACT_MODES, assert_exact_results, require_exact_mode
from tests._service_helpers import openapi_url, truncated_repr

NAMERES_TIMEOUT = 30
# Large enough that none of the queries below is truncated, so the modes' result sets can be
# compared with each other.
LIMIT = 100
# The most NameRes will return at once, for comparing the modes' complete result sets: a common
# gene symbol is an exact synonym of hundreds of orthologues.
MAX_LIMIT = 1000

PARKINSONIAN_DISORDER = 'MONDO:0021095'  # label 'parkinsonian disorder', synonym 'Parkinsonian Disease'
WOLFF_PARKINSON_WHITE = 'MONDO:0008685'  # label 'Wolff-Parkinson-White syndrome'
ALZHEIMER_DISEASE = 'MONDO:0004975'  # synonym "Alzheimer's disease", with an ASCII apostrophe

# (query, mode, CURIE that must be among the results)
EXACT_MATCHES = [
    ('parkinsonian disorder', 'label', PARKINSONIAN_DISORDER),
    ('parkinsonian disorder', 'synonyms', PARKINSONIAN_DISORDER),
    ('parkinsonian disorder', 'any', PARKINSONIAN_DISORDER),
    # Case-insensitive, and leading and trailing whitespace is stripped.
    ('  PARKINSONIAN DISORDER  ', 'label', PARKINSONIAN_DISORDER),
    # A synonym that is not the preferred name.
    ('Parkinsonian Disease', 'synonyms', PARKINSONIAN_DISORDER),
    ('Parkinsonian Disease', 'any', PARKINSONIAN_DISORDER),
    ('Wolff-Parkinson-White syndrome', 'label', WOLFF_PARKINSON_WHITE),
    ('Wolff Parkinson White syndrome', 'synonyms', WOLFF_PARKINSON_WHITE),
    ("Alzheimer's disease", 'synonyms', ALZHEIMER_DISEASE),
]

# (query, mode, CURIE that must *not* be among the results): the modes genuinely differ.
EXACT_MISSES = [
    # A synonym, but not the preferred name.
    ('Parkinsonian Disease', 'label', PARKINSONIAN_DISORDER),
    # The preferred name is hyphenated; only a synonym is spelled with spaces.
    ('Wolff Parkinson White syndrome', 'label', WOLFF_PARKINSON_WHITE),
]

# (query, CURIE): searches the default tokenized search answers with this CURIE, but which are not
# the whole of any of its names, so no exact mode may return it.
BROADER_SEARCHES = [
    ('parkinson', WOLFF_PARKINSON_WHITE),  # a single token of the name
    ('parkinsonian', PARKINSONIAN_DISORDER),  # a prefix
    ('Wolff-Parkinson-White', WOLFF_PARKINSON_WHITE),  # a prefix, punctuation and all
    ('parkinsonian disorders and syndromes', PARKINSONIAN_DISORDER),  # a superstring
    ('disorder parkinsonian', PARKINSONIAN_DISORDER),  # word order
    ('parkinsonian  disorder', PARKINSONIAN_DISORDER),  # internal whitespace is not collapsed
    ('parkinsonian-disorder', PARKINSONIAN_DISORDER),  # punctuation is not folded
    # The default search folds typographic quotes to ASCII; exact mode deliberately does not.
    ('Alzheimer’s disease', ALZHEIMER_DISEASE),
]

# Common searches whose exact-mode responses are checked against the definition of exact matching,
# on top of every query above.
COMMON_QUERIES = ['diabetes', 'asthma', 'aspirin', 'insulin', 'BRCA1', 'T']


@pytest.fixture
def nameres(target_info) -> CachedNameRes:
    require_exact_mode(target_info)
    return CachedNameRes.from_url(target_info['NameResURL'])


def curies(results):
    return [result['curie'] for result in results]


@pytest.mark.parametrize("query, mode, expected_curie", EXACT_MATCHES)
def test_exact_match(nameres, query, mode, expected_curie):
    results = nameres.lookup(query, exact=mode, limit=LIMIT)
    assert_exact_results(nameres, query, mode, results)
    assert expected_curie in curies(results), (
        f"{nameres} with exact={mode} for {query!r} did not return {expected_curie}: "
        f"{truncated_repr(curies(results))}"
    )


@pytest.mark.parametrize("query, mode, unexpected_curie", EXACT_MISSES)
def test_exact_miss(nameres, query, mode, unexpected_curie):
    results = nameres.lookup(query, exact=mode, limit=LIMIT)
    assert_exact_results(nameres, query, mode, results)
    assert unexpected_curie not in curies(results), (
        f"{nameres} with exact={mode} for {query!r} returned {unexpected_curie}, which has no "
        f"{'preferred name' if mode == 'label' else 'name'} equal to it."
    )


@pytest.mark.parametrize("query, curie", BROADER_SEARCHES)
def test_broader_search_no_longer_matches(nameres, query, curie):
    # First, the premise: without exact mode, this search does find the concept. Otherwise the
    # checks below would pass on a server that could not find it at all.
    default_results = nameres.lookup(query, limit=LIMIT)
    assert curie in curies(default_results), (
        f"{nameres} without exact mode no longer returns {curie} for {query!r} in its top {LIMIT}, "
        f"so this test no longer shows that exact mode narrows the search. Pick a query it does find."
    )

    for mode in EXACT_MODES:
        results = nameres.lookup(query, exact=mode, limit=LIMIT)
        assert_exact_results(nameres, query, mode, results)
        assert curie not in curies(results), (
            f"{nameres} with exact={mode} for {query!r} returned {curie}, although the query is not "
            f"the whole of any of its names."
        )


def all_queries():
    queries = [query for query, _, _ in EXACT_MATCHES + EXACT_MISSES]
    queries += [query for query, _ in BROADER_SEARCHES]
    queries += COMMON_QUERIES
    return list(dict.fromkeys(queries))


@pytest.mark.parametrize("query", all_queries())
def test_modes_are_consistent(nameres, query):
    """Every mode returns only exact matches, and `any` is exactly `label` plus `synonyms`."""
    results_by_mode = {}
    for mode in EXACT_MODES:
        results = nameres.lookup(query, exact=mode, limit=MAX_LIMIT)
        assert_exact_results(nameres, query, mode, results)
        if len(results) >= MAX_LIMIT:
            pytest.skip(f"{query!r} has at least {MAX_LIMIT} exact matches, so the modes cannot be compared.")
        results_by_mode[mode] = set(curies(results))

    assert results_by_mode['any'] == results_by_mode['label'] | results_by_mode['synonyms'], (
        f"{nameres} for {query!r}: exact=any returned {truncated_repr(sorted(results_by_mode['any']))}, "
        f"but label and synonyms together returned "
        f"{truncated_repr(sorted(results_by_mode['label'] | results_by_mode['synonyms']))}."
    )


def test_a_single_character_is_long_enough(nameres):
    # The minimum query length does not apply in exact mode, since one-character names (the gene
    # T, the element symbols) are real targets for it.
    results = nameres.lookup('T', exact='label', limit=LIMIT)
    assert results, f"{nameres} with exact=label for 'T' returned nothing."
    assert_exact_results(nameres, 'T', 'label', results)


def test_biolink_type_filter_applies(nameres):
    results = nameres.lookup('diabetes', exact='any', biolink_type='Disease', limit=LIMIT)
    assert_exact_results(nameres, 'diabetes', 'any', results)
    assert 'MONDO:0005015' in curies(results), (
        f"{nameres} with exact=any, biolink_type=Disease for 'diabetes' did not return "
        f"MONDO:0005015 (diabetes mellitus): {truncated_repr(curies(results))}"
    )
    for result in results:
        assert 'biolink:Disease' in result['types'], (
            f"{nameres} with biolink_type=Disease returned {result['curie']} with types "
            f"{truncated_repr(result['types'])}"
        )

    # The filter must actually remove something, or this test would pass on a server ignoring it.
    unfiltered = nameres.lookup('diabetes', exact='any', limit=LIMIT)
    assert len(unfiltered) > len(results), (
        f"{nameres} with exact=any for 'diabetes' returned the same {len(results)} results with and "
        f"without biolink_type=Disease, so this test no longer shows that the filter applies."
    )


def test_prefix_filter_applies(nameres):
    results = nameres.lookup('diabetes', exact='any', only_prefixes='MONDO', limit=LIMIT)
    assert results, f"{nameres} with exact=any, only_prefixes=MONDO for 'diabetes' returned nothing."
    assert_exact_results(nameres, 'diabetes', 'any', results)
    assert all(curie.startswith('MONDO:') for curie in curies(results)), (
        f"{nameres} with only_prefixes=MONDO returned {truncated_repr(curies(results))}"
    )


def test_pagination(nameres):
    everything = curies(nameres.lookup('diabetes', exact='any', limit=LIMIT))
    assert len(everything) >= 2, f"{nameres} with exact=any for 'diabetes' returned fewer than two results."
    second = curies(nameres.lookup('diabetes', exact='any', offset=1, limit=1))
    assert second == everything[1:2]


def test_highlighting_marks_the_whole_name(nameres):
    results = nameres.lookup('Parkinsonian Disease', exact='synonyms', highlighting='true', limit=LIMIT)
    assert PARKINSONIAN_DISORDER in curies(results)
    for result in results:
        highlighting = result['highlighting']
        # Only the synonyms were searched, so only synonyms may be highlighted.
        assert highlighting['labels'] == [], f"{result['curie']} has label highlights in exact=synonyms mode: {highlighting}"
        assert highlighting['synonyms'], f"{result['curie']} has no synonym highlights: {highlighting}"
        for highlight in highlighting['synonyms']:
            assert highlight.startswith('<strong>') and highlight.endswith('</strong>'), (
                f"{result['curie']} has a highlight that does not cover the whole name: {highlight!r}"
            )
            name = highlight.removeprefix('<strong>').removesuffix('</strong>')
            assert name in result['synonyms'] and name.lower() == 'parkinsonian disease', (
                f"{result['curie']} highlights {highlight!r}, which is not one of its synonyms equal to the query."
            )


@pytest.mark.parametrize("mode", EXACT_MODES)
def test_bulk_lookup_matches_lookup(nameres, mode):
    queries = ['parkinsonian disorder', 'Parkinsonian Disease', 'Wolff Parkinson White syndrome', 'parkinson', 'diabetes']
    bulk = nameres.bulk_lookup(queries, exact=mode, limit=LIMIT)
    for query in queries:
        single = nameres.lookup(query, exact=mode, limit=LIMIT)
        assert_exact_results(nameres, query, mode, bulk[query])
        assert curies(bulk[query]) == curies(single), (
            f"{nameres} with exact={mode} for {query!r}: /bulk-lookup returned "
            f"{truncated_repr(curies(bulk[query]))}, but /lookup returned {truncated_repr(curies(single))}."
        )


def test_bulk_lookup_maps_empty_strings_to_no_results(nameres):
    bulk = nameres.bulk_lookup(['', ' ', 'parkinsonian disorder'], exact='any', limit=LIMIT)
    assert bulk[''] == []
    assert bulk[' '] == []
    assert PARKINSONIAN_DISORDER in curies(bulk['parkinsonian disorder'])


# Rejections are checked with requests directly: CachedNameRes raises on any error status.

def lookup_url(target_info):
    return urllib.parse.urljoin(target_info['NameResURL'], 'lookup')


def bulk_lookup_url(target_info):
    return urllib.parse.urljoin(target_info['NameResURL'], 'bulk-lookup')


@pytest.mark.parametrize("params, expected_status", [
    # autocomplete treats the last word as a prefix; exact requires the whole string.
    ({'string': 'diabetes', 'exact': 'any', 'autocomplete': 'true'}, 400),
    ({'string': 'diabetes', 'exact': 'bogus'}, 422),
    # The modes are case-sensitive.
    ({'string': 'diabetes', 'exact': 'LABEL'}, 422),
    # No minimum length in exact mode, but an empty string is still rejected.
    ({'string': '', 'exact': 'label'}, 422),
    ({'string': '   ', 'exact': 'label'}, 422),
], ids=['autocomplete', 'unknown-mode', 'uppercase-mode', 'empty', 'whitespace'])
def test_lookup_rejects(target_info, params, expected_status):
    require_exact_mode(target_info)
    url = lookup_url(target_info)
    for method in (requests.get, requests.post):
        response = method(url, params=params, timeout=NAMERES_TIMEOUT)
        assert response.status_code == expected_status, (
            f"{method.__name__.upper()} {url} with {params} returned HTTP {response.status_code} "
            f"instead of {expected_status}: {truncated_repr(response.text)}"
        )


@pytest.mark.parametrize("body, expected_status", [
    ({'strings': ['diabetes'], 'exact': 'any', 'autocomplete': True}, 400),
    ({'strings': ['diabetes'], 'exact': 'bogus'}, 422),
    ({'strings': ['diabetes'], 'exact': 'LABEL'}, 422),
], ids=['autocomplete', 'unknown-mode', 'uppercase-mode'])
def test_bulk_lookup_rejects(target_info, body, expected_status):
    require_exact_mode(target_info)
    url = bulk_lookup_url(target_info)
    response = requests.post(url, json=body, timeout=NAMERES_TIMEOUT)
    assert response.status_code == expected_status, (
        f"POST {url} with {body} returned HTTP {response.status_code} instead of "
        f"{expected_status}: {truncated_repr(response.text)}"
    )


def test_openapi_declares_exact(target_info):
    require_exact_mode(target_info)
    url = openapi_url(target_info, 'NameResURL', 'NameResOpenAPIPath')
    response = requests.get(url, timeout=NAMERES_TIMEOUT)
    assert response.ok, f"Could not GET {url}: {response}"
    openapi_json = response.json()
    schemas = openapi_json['components']['schemas']

    def enum_of(schema):
        # FastAPI renders Optional[ExactMatchMode] as anyOf: [{$ref: ExactMatchMode}, {type: null}].
        for option in schema.get('anyOf', [schema]):
            if '$ref' in option:
                return set(schemas[option['$ref'].rsplit('/', 1)[-1]].get('enum', []))
        return set()

    for method in ('get', 'post'):
        parameters = {p['name']: p for p in openapi_json['paths']['/lookup'][method]['parameters']}
        assert 'exact' in parameters, f"{url} does not declare an exact parameter on {method.upper()} /lookup"
        assert enum_of(parameters['exact']['schema']) == set(EXACT_MODES), (
            f"{url} declares exact on {method.upper()} /lookup as {truncated_repr(parameters['exact'])}"
        )

    query_properties = schemas['NameResQuery']['properties']
    assert 'exact' in query_properties, f"{url} does not declare exact in NameResQuery"
    assert enum_of(query_properties['exact']) == set(EXACT_MODES), (
        f"{url} declares NameResQuery.exact as {truncated_repr(query_properties['exact'])}"
    )
