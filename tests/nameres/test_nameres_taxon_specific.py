#!/usr/bin/env python3
#
# In https://github.com/NCATSTranslator/NameResolution/pull/214, NameRes added a taxon_specific flag, which
# can be used to ensure that non-taxon-specific results are not filtered out when only_taxa is applied
# (e.g. searching for `diabetes` should always return MONDO:0005015, even if `only_taxa=NCBITaxon:9606` is set.
# see https://github.com/NCATSTranslator/NameResolution/issues/193 for more details). These tests check this
# behavior.
#
# They assert what only_taxa does to the results, not which concept ranks first: the top hit for `diabetes` was
# once UMLS:C0011847, until a Babel release merged that CURIE into another clique. Nor do they name a concept
# with no taxa, since which concepts have taxa changes between Babel releases too
# (https://github.com/NCATSTranslator/Babel/issues/1168).
import re

import pytest
import requests

from tests._service_helpers import truncated_repr

DIABETES_MELLITUS = 'MONDO:0005015'
HUMAN = 'NCBITaxon:9606'
MOUSE = 'NCBITaxon:10090'

# Enough results to reach the concepts from other species that only_taxa should remove.
LOOKUP_LIMIT = 200

# The first NameRes release that consults taxon_specific. Compare version numbers, not release dates: v1.5.2, which
# does not have the flag, was released after v1.6.x. And check the NameRes version rather than the Babel release:
# this is NameRes behaviour, and CI has served Babel 2026jul22 through NameRes v1.5.2.
FIRST_TAXON_SPECIFIC_VERSION = (1, 6, 0)
NAMERES_VERSION_RE = re.compile(r'v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})')


def supports_taxon_specific(nameres_version):
    match = NAMERES_VERSION_RE.fullmatch(nameres_version) if isinstance(nameres_version, str) else None
    return match is not None and tuple(map(int, match.groups())) >= FIRST_TAXON_SPECIFIC_VERSION


def require_taxon_specific(target_info):
    """
    Skip the calling test on a NameRes too old to have the taxon_specific behaviour.

    A /status that cannot be fetched is an error rather than a skip, so that a broken deployment does not look like an
    old one. A NameRes that reports no recognizable version is skipped, since it cannot say what it supports.
    """
    response = requests.get(target_info['NameResURL'] + 'status')
    response.raise_for_status()
    nameres_version = response.json().get('nameres_version')
    if not supports_taxon_specific(nameres_version):
        pytest.skip(
            f"NameRes reports nameres_version {truncated_repr(nameres_version)}; "
            f"only_taxa needs v{'.'.join(map(str, FIRST_TAXON_SPECIFIC_VERSION))} or later to keep concepts with no taxa"
        )


def lookup_diabetes(target_info, **params):
    response = requests.get(target_info['NameResURL'] + 'lookup', params={'string': 'diabetes', **params})
    response.raise_for_status()
    return response.json()


@pytest.mark.unit
@pytest.mark.parametrize('nameres_version,expected', [
    ('v1.6.0', True),
    ('1.6.0', True),
    ('v1.7.1', True),
    ('v1.10.0', True),
    ('v2.0.0', True),
    ('v1.5.2', False),
    ('v1.5.10', False),
    ('v0.9.9', False),
    ('latest', False),
    ('', False),
    (None, False),
    (1.7, False),
])
def test_supports_taxon_specific(nameres_version, expected):
    assert supports_taxon_specific(nameres_version) is expected


def test_taxon_specific_diabetes_without_only_taxa(target_info):
    curies = [result['curie'] for result in lookup_diabetes(target_info)]
    assert DIABETES_MELLITUS in curies


def test_taxon_specific_diabetes_with_only_taxa(target_info):
    require_taxon_specific(target_info)

    results = lookup_diabetes(target_info, only_taxa=HUMAN, limit=LOOKUP_LIMIT)

    assert DIABETES_MELLITUS in [result['curie'] for result in results]
    # This is what taxon_specific is for: before it, only_taxa returned nothing but genes and proteins.
    assert any(not result['taxa'] for result in results), 'only_taxa removed every concept with no taxa'
    # ...and only_taxa must still filter.
    assert [result['curie'] for result in results if result['taxa'] and HUMAN not in result['taxa']] == []


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason='Babel tags MONDO:0005015 as human-only: https://github.com/NCATSTranslator/Babel/issues/1168',
)
def test_taxon_specific_diabetes_with_only_taxa_for_another_species(target_info):
    require_taxon_specific(target_info)

    curies = [result['curie'] for result in lookup_diabetes(target_info, only_taxa=MOUSE, limit=LOOKUP_LIMIT)]

    assert DIABETES_MELLITUS in curies
