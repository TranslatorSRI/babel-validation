#
# Tests for the NodeNorm descriptions
#
import pytest
import requests

IDENTIFIERS_WITH_DESCRIPTIONS = {
    'MESH:D014867',
    'NCIT:C34373',
    'NCBIGene:1756',
    'UMLS:C0665297',
}
@pytest.mark.parametrize('curie', IDENTIFIERS_WITH_DESCRIPTIONS)
def test_descriptions(target_info, curie):
    """ Look up a few identifiers known to have descriptions. """
    nodenorm_url = target_info['NodeNormURL']

    response = requests.get(f'https://{nodenorm_url}/get_normalized_nodes', params={'curie': curie})
    response.raise_for_status()
    result = response.json()

    assert curie in result

    curie_result = result[curie]
    assert 'description' in curie_result['identifier']
    assert curie_result['identifier']['description'] != ''

    assert 'descriptions' in curie_result
    assert len(curie_result['descriptions']) > 0


IDENTIFIERS_WITHOUT_DESCRIPTIONS = {
    'UMLS:C0665297',        # natalizumab
}
@pytest.mark.parametrize('curie', IDENTIFIERS_WITHOUT_DESCRIPTIONS)
def test_no_descriptions(target_info, curie):
    """ Look up a few identifiers that don't have descriptions. """
    nodenorm_url = target_info['NodeNormURL']

    response = requests.get(f'https://{nodenorm_url}/get_normalized_nodes', params={'curie': curie})
    response.raise_for_status()
    result = response.json()

    assert curie in result

    curie_result = result[curie]
    assert 'description' not in curie_result['identifier']
    assert 'descriptions' not in curie_result
