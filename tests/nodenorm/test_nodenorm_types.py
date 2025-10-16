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
        "NCBIGene:22059": [
            'biolink:Gene',
            'biolink:GeneOrGeneProduct',
            'biolink:GenomicEntity',
            'biolink:ChemicalEntityOrGeneOrGeneProduct',
            'biolink:PhysicalEssence',
            'biolink:OntologyClass',
            'biolink:BiologicalEntity',
            'biolink:ThingWithTaxon',
            'biolink:NamedThing',
            'biolink:PhysicalEssenceOrOccurrent',
            'biolink:MacromolecularMachineMixin'
        ],
        "UNII:K16AIQ8CTM": [
            'biolink:ChemicalEntity',
            'biolink:PhysicalEssence',
            'biolink:ChemicalOrDrugOrTreatment',
            'biolink:ChemicalEntityOrGeneOrGeneProduct',
            'biolink:ChemicalEntityOrProteinOrPolypeptide',
            'biolink:NamedThing',
            'biolink:PhysicalEssenceOrOccurrent'
        ],
        "PR:Q9Y6J0": [
            'biolink:Protein',
            'biolink:GeneProductMixin',
            'biolink:Polypeptide',
            'biolink:ChemicalEntityOrGeneOrGeneProduct',
            'biolink:ChemicalEntityOrProteinOrPolypeptide',
            'biolink:BiologicalEntity',
            'biolink:ThingWithTaxon',
            'biolink:NamedThing',
            'biolink:GeneOrGeneProduct',
            'biolink:MacromolecularMachineMixin'
        ],
        "GO:0003990": [
            'biolink:MolecularActivity',
            'biolink:Occurrent',
            'biolink:OntologyClass',
            'biolink:BiologicalProcessOrActivity',
            'biolink:BiologicalEntity',
            'biolink:ThingWithTaxon',
            'biolink:NamedThing',
            'biolink:PhysicalEssenceOrOccurrent'
        ]
    }

    response = requests.post(nodenorm_url + "get_normalized_nodes", json={
        "curies": list(curies_and_expected_results.keys()),
        "conflate": False,
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


def test_geneprotein_conflated_biolink_types(nodenorm_url):
    """
    Check a few Biolink types with GeneProtein conflation turned on.
    """
    curies_and_expected_results = {
        "NCBIGene:22059": [
            'biolink:Gene',
            'biolink:GeneOrGeneProduct',
            'biolink:GenomicEntity',
            'biolink:ChemicalEntityOrGeneOrGeneProduct',
            'biolink:PhysicalEssence',
            'biolink:OntologyClass',
            'biolink:BiologicalEntity',
            'biolink:ThingWithTaxon',
            'biolink:NamedThing',
            'biolink:PhysicalEssenceOrOccurrent',
            'biolink:MacromolecularMachineMixin',
            'biolink:Protein',
            'biolink:GeneProductMixin',
            'biolink:Polypeptide',
            'biolink:ChemicalEntityOrProteinOrPolypeptide'
        ],
        "PR:Q9Y6J0": [
            'biolink:Gene',
            'biolink:GeneOrGeneProduct',
            'biolink:GenomicEntity',
            'biolink:ChemicalEntityOrGeneOrGeneProduct',
            'biolink:PhysicalEssence',
            'biolink:OntologyClass',
            'biolink:BiologicalEntity',
            'biolink:ThingWithTaxon',
            'biolink:NamedThing',
            'biolink:PhysicalEssenceOrOccurrent',
            'biolink:MacromolecularMachineMixin',
            'biolink:Protein',
            'biolink:GeneProductMixin',
            'biolink:Polypeptide',
            'biolink:ChemicalEntityOrProteinOrPolypeptide',
        ]
    }

    response = requests.post(nodenorm_url + "get_normalized_nodes", json={
        "curies": list(curies_and_expected_results.keys()),
        "conflate": True,
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

        # Check the individual types, which -- with GeneProtein conflation -- should be either 'biolink:Gene' or 'biolink:Protein'.
        for equivalent_identifiers in result['equivalent_identifiers']:
            assert equivalent_identifiers['type'] in {'biolink:Gene', 'biolink:Protein'}


def test_drugchemical_conflated_biolink_types(nodenorm_url):
    """
    Check a few Biolink types with DrugChemical conflation turned on.
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
            "biolink:PhysicalEssenceOrOccurrent",
            'biolink:Drug',
            'biolink:OntologyClass',
            'biolink:MolecularMixture',
            'biolink:ChemicalMixture',
        ],
        "UNII:K16AIQ8CTM": [
            'biolink:ChemicalEntity',
            'biolink:PhysicalEssence',
            'biolink:ChemicalOrDrugOrTreatment',
            'biolink:ChemicalEntityOrGeneOrGeneProduct',
            'biolink:ChemicalEntityOrProteinOrPolypeptide',
            'biolink:NamedThing',
            'biolink:PhysicalEssenceOrOccurrent',
            'biolink:Drug',
            'biolink:OntologyClass',
            'biolink:MolecularMixture',
            'biolink:ChemicalMixture',
        ]
    }

    response = requests.post(nodenorm_url + "get_normalized_nodes", json={
        "curies": list(curies_and_expected_results.keys()),
        "conflate": False,
        "drug_chemical_conflate": True,
        "individual_types": True,
    })
    results = response.json()

    # Pull out each Biolink types list and compare to expected results.
    for query_curie in curies_and_expected_results.keys():
        result = results[query_curie]

        # Compare Biolink types with expected results.
        biolink_types = result['type']
        assert biolink_types == curies_and_expected_results[query_curie]

        # Check the individual types, which -- without conflation -- should be one of the chemical types.
        first_biolink_type = biolink_types[0]
        for equivalent_identifiers in result['equivalent_identifiers']:
            assert equivalent_identifiers['type'] in {
                'biolink:Drug',
                'biolink:SmallMolecule',
                'biolink:ChemicalEntity',
            }



def test_fully_conflated_biolink_types(nodenorm_url):
    """
    Check a few Biolink types with conflation fully turned on.
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
            "biolink:PhysicalEssenceOrOccurrent",
            'biolink:Drug',
            'biolink:OntologyClass',
            'biolink:MolecularMixture',
            'biolink:ChemicalMixture',
        ],
        "NCIT:C34373": [
            "biolink:Disease",
            "biolink:DiseaseOrPhenotypicFeature",
            "biolink:BiologicalEntity",
            "biolink:ThingWithTaxon",
            "biolink:NamedThing"
        ],
        "NCBIGene:22059": [
            'biolink:Gene',
            'biolink:GeneOrGeneProduct',
            'biolink:GenomicEntity',
            'biolink:ChemicalEntityOrGeneOrGeneProduct',
            'biolink:PhysicalEssence',
            'biolink:OntologyClass',
            'biolink:BiologicalEntity',
            'biolink:ThingWithTaxon',
            'biolink:NamedThing',
            'biolink:PhysicalEssenceOrOccurrent',
            'biolink:MacromolecularMachineMixin',
            'biolink:Protein',
            'biolink:GeneProductMixin',
            'biolink:Polypeptide',
            'biolink:ChemicalEntityOrProteinOrPolypeptide',
        ],
        "UNII:K16AIQ8CTM": [
            'biolink:ChemicalEntity',
            'biolink:PhysicalEssence',
            'biolink:ChemicalOrDrugOrTreatment',
            'biolink:ChemicalEntityOrGeneOrGeneProduct',
            'biolink:ChemicalEntityOrProteinOrPolypeptide',
            'biolink:NamedThing',
            'biolink:PhysicalEssenceOrOccurrent',
            'biolink:Drug',
            'biolink:OntologyClass',
            'biolink:MolecularMixture',
            'biolink:ChemicalMixture',
        ],
        "PR:Q9Y6J0": [
            'biolink:Gene',
            'biolink:GeneOrGeneProduct',
            'biolink:GenomicEntity',
            'biolink:ChemicalEntityOrGeneOrGeneProduct',
            'biolink:PhysicalEssence',
            'biolink:OntologyClass',
            'biolink:BiologicalEntity',
            'biolink:ThingWithTaxon',
            'biolink:NamedThing',
            'biolink:PhysicalEssenceOrOccurrent',
            'biolink:MacromolecularMachineMixin',
            'biolink:Protein',
            'biolink:GeneProductMixin',
            'biolink:Polypeptide',
            'biolink:ChemicalEntityOrProteinOrPolypeptide',
        ],
        "GO:0003990": [
            'biolink:MolecularActivity',
            'biolink:Occurrent',
            'biolink:OntologyClass',
            'biolink:BiologicalProcessOrActivity',
            'biolink:BiologicalEntity',
            'biolink:ThingWithTaxon',
            'biolink:NamedThing',
            'biolink:PhysicalEssenceOrOccurrent'
        ]
    }

    response = requests.post(nodenorm_url + "get_normalized_nodes", json={
        "curies": list(curies_and_expected_results.keys()),
        "conflate": True,
        "drug_chemical_conflate": True,
        "individual_types": True,
    })
    results = response.json()

    # Pull out each Biolink types list and compare to expected results.
    for query_curie in curies_and_expected_results.keys():
        result = results[query_curie]

        # Compare Biolink types with expected results.
        biolink_types = result['type']
        assert biolink_types == curies_and_expected_results[query_curie]

        # Check the individual types, which -- with full conflation -- should be one of the Biolink types for the overall clique.
        for equivalent_identifiers in result['equivalent_identifiers']:
            assert equivalent_identifiers['type'] in biolink_types
