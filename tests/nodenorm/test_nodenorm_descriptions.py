#
# Tests for the NodeNorm descriptions
# Note that these tests are for NodeNorm v2.3.28 onwards, as they assume a top-level `descriptions` key with a list
# of all unique descriptions for a clique.
#
import pytest
import requests

IDENTIFIERS_WITH_DESCRIPTIONS = {
    'MESH:D014867',
    'NCIT:C34373',
    'NCBIGene:1756',
}

IDENTIFIERS_WITHOUT_DESCRIPTIONS = {
    'UMLS:C0665297',        # natalizumab
}

@pytest.mark.parametrize('curie', IDENTIFIERS_WITH_DESCRIPTIONS)
def test_descriptions(target_info, curie):
    """ Look up a few identifiers known to have descriptions. """
    nodenorm_url = target_info['NodeNormURL']

    # Make sure we get descriptions if we set the description flag for this CURIE.
    response = requests.post(nodenorm_url + 'get_normalized_nodes', json={
        'curies': [curie],
        'description': True,
    })
    response.raise_for_status()
    result = response.json()

    assert curie in result

    curie_result = result[curie]
    assert 'description' in curie_result['id']
    assert curie_result['id']['description'] != ''

    assert 'descriptions' in curie_result
    assert len(curie_result['descriptions']) > 0

    # Make sure we don't get this response if the description flag is false.
    response = requests.post(nodenorm_url + 'get_normalized_nodes', json={
        'curies': [curie],
        'description': False,
    })
    response.raise_for_status()
    result = response.json()

    assert curie in result
    curie_result = result[curie]
    assert 'description' not in curie_result['id']
    assert 'descriptions' not in curie_result


@pytest.mark.parametrize('curie', IDENTIFIERS_WITHOUT_DESCRIPTIONS)
@pytest.mark.parametrize('description_flag', ['false', 'true'])
def test_no_descriptions(target_info, curie, description_flag):
    """ Look up a few identifiers that don't have descriptions. """
    nodenorm_url = target_info['NodeNormURL']

    response = requests.get(nodenorm_url + 'get_normalized_nodes', params={'curie': curie, 'description': description_flag})
    response.raise_for_status()
    result = response.json()

    assert curie in result

    curie_result = result[curie]
    assert 'description' not in curie_result['id']
    assert 'descriptions' not in curie_result
