#!/usr/bin/env python3
#
# In https://github.com/NCATSTranslator/NameResolution/pull/214, NameRes added a taxon_specific flag, which
# can be used to ensure that non-taxon-specific results are not filtered out when only_taxa is applied
# (e.g. searching for `diabetes` should always return MONDO:0005015, even if `only_taxa=NCBITaxon:9606` is set.
# see https://github.com/NCATSTranslator/NameResolution/issues/193 for more details). These tests check this
# behavior.
import requests


def test_taxon_specific_diabetes_without_only_taxa(target_info):
    nameres_url = target_info['NameResURL']

    response = requests.get(nameres_url + 'lookup', params={'string': 'diabetes'})
    response.raise_for_status()
    best_result = response.json()[0]
    assert best_result['curie'] == 'UMLS:C0011847'

def test_taxon_specific_diabetes_with_only_taxa(target_info):
    nameres_url = target_info['NameResURL']

    response = requests.get(nameres_url + 'lookup', params={'string': 'diabetes', 'only_taxa': 'NCBITaxon:9606'})
    response.raise_for_status()
    best_result = response.json()[0]
    assert best_result['curie'] == 'UMLS:C0011847'
