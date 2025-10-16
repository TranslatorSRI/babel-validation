#
# Tests for the NodeNorm API Biolink types.
# These aren't covered in the GSheet tests, because those mostly check whether the first (most specific) Biolink type
# is correct. These tests are intended to cover whether all the Biolink types are correct, for both normal entries
# and conflated entries.
#

import pytest
import requests

@pytest.fixture
def nodenorm_url(target_info):
    return target_info['NodeNormURL']

def test_unconflated_biolink_types(nodenorm_url):
    """
    Check a few Biolink types without conflation turned on.
    """
    curies_and_expected_results = {
        "MESH:D014867": [
            "biolink:SmallMolecule",
            "biolink:MolecularEntity",
            "biolink:ChemicalEntity",
            "biolink:PhysicalEssence",
            "biolink:ChemicalOrDrugOrTreatment",
            "biolink:ChemicalEntityOrGeneOrGeneProduct",
            "biolink:ChemicalEntityOrProteinOrPolypeptide",
            "biolink:NamedThing",
            "biolink:PhysicalEssenceOrOccurrent"
        ],
        "NCIT:C34373": [
            "biolink:Disease",
            "biolink:DiseaseOrPhenotypicFeature",
            "biolink:BiologicalEntity",
            "biolink:ThingWithTaxon",
            "biolink:NamedThing"
        ],
    }

    response = requests.post(nodenorm_url + "get_normalized_nodes", json={
        "curies": list(curies_and_expected_results.keys()),
        "conflate": False,
        "description": False,
        "drug_chemical_conflate": False,
        "individual_types": True,
    })
    results = response.json()

    # Pull out each Biolink types list and compare to expected results.
    for query_curie in curies_and_expected_results.keys():
        result = results[query_curie]

        # Compare Biolink types with expected results.
        biolink_types = result['type']
        assert biolink_types == curies_and_expected_results[query_curie]

        # Check the individual types, which -- without conflation -- should be identical to the first Biolink type.
        first_biolink_type = biolink_types[0]
        for equivalent_identifiers in result['equivalent_identifiers']:
            assert equivalent_identifiers['type'] == first_biolink_type
