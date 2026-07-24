#
# Tests for the NodeNorm API Biolink types.
# These aren't covered in the GSheet tests, because those mostly check whether the first (most specific) Biolink type
# is correct. These tests are intended to cover whether all the Biolink types are correct, for both normal entries
# and conflated entries.
#
# The expected values below are the baseline as of NodeNorm on `exp` (2026-07-24). They differ from
# dev/prod/test/ci, which still return the previous baseline; see the PR discussion for whether these
# changes should be accepted or fixed in NodeNorm. The three differences are:
#   1. `biolink:OntologyClass` is now included for cliques that previously lacked it (MESH:D014867,
#      NCIT:C34373), inserted after the second-most-specific type.
#   2. `biolink:GeneOrGeneProductOrGeneFamily` is a new type on gene cliques, after
#      `biolink:GeneOrGeneProduct`.
#   3. Because of (1), `biolink:OntologyClass` now appears in the main clique's types for
#      MESH:D014867 rather than being appended by DrugChemical conflation, so its position moves.
#

import pytest
import requests

@pytest.fixture
def nodenorm_url(target_info):
    return target_info['NodeNormURL']


def check_biolink_types(nodenorm_url, expected, conflate, drug_chemical_conflate, allowed_individual_types):
    """
    Query get_normalized_nodes for every CURIE in `expected` and compare the returned Biolink types.

    Every mismatch across every CURIE is collected and reported in a single assertion, so that one
    bad clique doesn't hide the others. `allowed_individual_types` is called with the types actually
    returned for the clique and should return the set of types each equivalent identifier may have.
    """
    response = requests.post(nodenorm_url + "get_normalized_nodes", json={
        "curies": list(expected.keys()),
        "conflate": conflate,
        "drug_chemical_conflate": drug_chemical_conflate,
        "individual_types": True,
    })
    response.raise_for_status()
    results = response.json()

    errors = []
    for curie, expected_types in expected.items():
        result = results.get(curie)
        if result is None:
            errors.append(f"{curie}: no result returned")
            continue

        actual_types = result['type']
        if actual_types != expected_types:
            missing = [t for t in expected_types if t not in actual_types]
            extra = [t for t in actual_types if t not in expected_types]
            reordered = not missing and not extra
            errors.append(
                f"{curie}: Biolink types differ ({'reordered only' if reordered else 'membership differs'})\n"
                f"  expected: {expected_types}\n"
                f"  actual:   {actual_types}\n"
                f"  missing from actual: {missing}\n"
                f"  unexpected in actual: {extra}"
            )

        allowed = allowed_individual_types(actual_types)
        for eq in result['equivalent_identifiers']:
            if eq['type'] not in allowed:
                errors.append(
                    f"{curie}: equivalent identifier {eq['identifier']} has type {eq['type']}, "
                    f"expected one of {sorted(allowed)}"
                )

    assert not errors, f"{len(errors)} difference(s) found:\n\n" + "\n\n".join(errors)


def test_unconflated_biolink_types(nodenorm_url):
    """
    Check a few Biolink types without conflation turned on.
    """
    curies_and_expected_results = {
        "MESH:D014867": [
            "biolink:SmallMolecule",
            "biolink:MolecularEntity",
            "biolink:OntologyClass",
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
            "biolink:OntologyClass",
            "biolink:BiologicalEntity",
            "biolink:ThingWithTaxon",
            "biolink:NamedThing"
        ],
        "NCBIGene:22059": [
            'biolink:Gene',
            'biolink:GeneOrGeneProduct',
            'biolink:GeneOrGeneProductOrGeneFamily',
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

    # Without conflation, every individual type should be identical to the first Biolink type.
    check_biolink_types(
        nodenorm_url,
        curies_and_expected_results,
        conflate=False,
        drug_chemical_conflate=False,
        allowed_individual_types=lambda actual_types: {actual_types[0]},
    )


def test_geneprotein_conflated_biolink_types(nodenorm_url):
    """
    Check a few Biolink types with GeneProtein conflation turned on.
    """
    curies_and_expected_results = {
        "NCBIGene:22059": [
            'biolink:Gene',
            'biolink:GeneOrGeneProduct',
            'biolink:GeneOrGeneProductOrGeneFamily',
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
            'biolink:GeneOrGeneProductOrGeneFamily',
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

    # With GeneProtein conflation, every individual type should be either 'biolink:Gene' or 'biolink:Protein'.
    check_biolink_types(
        nodenorm_url,
        curies_and_expected_results,
        conflate=True,
        drug_chemical_conflate=False,
        allowed_individual_types=lambda actual_types: {'biolink:Gene', 'biolink:Protein'},
    )


def test_drugchemical_conflated_biolink_types(nodenorm_url):
    """
    Check a few Biolink types with DrugChemical conflation turned on.
    """
    curies_and_expected_results = {
        "MESH:D014867": [
            "biolink:SmallMolecule",
            "biolink:MolecularEntity",
            "biolink:OntologyClass",
            "biolink:ChemicalEntity",
            "biolink:PhysicalEssence",
            "biolink:ChemicalOrDrugOrTreatment",
            "biolink:ChemicalEntityOrGeneOrGeneProduct",
            "biolink:ChemicalEntityOrProteinOrPolypeptide",
            "biolink:NamedThing",
            "biolink:PhysicalEssenceOrOccurrent",
            'biolink:Drug',
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

    # With DrugChemical conflation, every individual type should be one of the chemical types.
    check_biolink_types(
        nodenorm_url,
        curies_and_expected_results,
        conflate=False,
        drug_chemical_conflate=True,
        allowed_individual_types=lambda actual_types: {
            'biolink:Drug',
            'biolink:SmallMolecule',
            'biolink:ChemicalEntity',
        },
    )



def test_fully_conflated_biolink_types(nodenorm_url):
    """
    Check a few Biolink types with conflation fully turned on.
    """
    curies_and_expected_results = {
        "MESH:D014867": [
            "biolink:SmallMolecule",
            "biolink:MolecularEntity",
            "biolink:OntologyClass",
            "biolink:ChemicalEntity",
            "biolink:PhysicalEssence",
            "biolink:ChemicalOrDrugOrTreatment",
            "biolink:ChemicalEntityOrGeneOrGeneProduct",
            "biolink:ChemicalEntityOrProteinOrPolypeptide",
            "biolink:NamedThing",
            "biolink:PhysicalEssenceOrOccurrent",
            'biolink:Drug',
            'biolink:MolecularMixture',
            'biolink:ChemicalMixture',
        ],
        "NCIT:C34373": [
            "biolink:Disease",
            "biolink:DiseaseOrPhenotypicFeature",
            "biolink:OntologyClass",
            "biolink:BiologicalEntity",
            "biolink:ThingWithTaxon",
            "biolink:NamedThing"
        ],
        "NCBIGene:22059": [
            'biolink:Gene',
            'biolink:GeneOrGeneProduct',
            'biolink:GeneOrGeneProductOrGeneFamily',
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
            'biolink:GeneOrGeneProductOrGeneFamily',
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

    # With full conflation, every individual type should be one of the Biolink types for the overall clique.
    check_biolink_types(
        nodenorm_url,
        curies_and_expected_results,
        conflate=True,
        drug_chemical_conflate=True,
        allowed_individual_types=set,
    )
