# This is a test for https://github.com/TranslatorSRI/NodeNormalization/issues/229

import requests
import urllib


def test_nodenorm_229(target_info):
    nodenorm_url = target_info["NodeNormURL"]

    input_json = {
        "message": {
            "query_graph": {
                "nodes": {
                    "n0": {
                        "categories": ["biolink:Drug"],
                        "is_set": False,
                        "constraints": [],
                    },
                    "n1": {
                        "ids": ["MONDO:0001134"],
                        "categories": ["biolink:Disease"],
                        "is_set": False,
                        "constraints": [],
                    },
                },
                "edges": {
                    "e01": {
                        "subject": "n0",
                        "object": "n1",
                        "predicates": ["biolink:treats"],
                        "attribute_constraints": [],
                        "qualifier_constraints": [],
                    }
                },
            },
            "knowledge_graph": {
                "nodes": {
                    "DRUGBANK:DB00275": {
                        "categories": ["biolink:Drug"],
                        "name": "Olmesartan",
                    },
                    "MONDO:0001134": {
                        "categories": ["biolink:Disease"],
                        "name": "essential hypertension",
                    },
                    "DRUGBANK:DB00876": {
                        "categories": ["biolink:Drug"],
                        "name": "Eprosartan",
                    },
                    "DRUGBANK:DB00177": {
                        "categories": ["biolink:Drug"],
                        "name": "Valsartan",
                    },
                    "DRUGBANK:DB00966": {
                        "categories": ["biolink:Drug"],
                        "name": "Telmisartan",
                    },
                    "DRUGBANK:DB00678": {
                        "categories": ["biolink:Drug"],
                        "name": "Losartan",
                    },
                },
                "edges": {
                    "e0": {
                        "subject": "DRUGBANK:DB00275",
                        "object": "MONDO:0001134",
                        "predicate": "biolink:treats",
                        "sources": [
                            {
                                "resource_id": "infores:openpredict",
                                "resource_role": "primary_knowledge_source",
                            },
                            {
                                "resource_id": "infores:cohd",
                                "resource_role": "supporting_data_source",
                            },
                        ],
                        "attributes": [
                            {
                                "description": "model_id",
                                "attribute_type_id": "EDAM:data_1048",
                                "value": "openpredict_baseline",
                            },
                            {
                                "attribute_type_id": "biolink:agent_type",
                                "value": "computational_model",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "biolink:knowledge_level",
                                "value": "prediction",
                                "attribute_source": "infores:openpredict",
                            },
                        ],
                    },
                    "e1": {
                        "subject": "DRUGBANK:DB00876",
                        "object": "MONDO:0001134",
                        "predicate": "biolink:treats",
                        "sources": [
                            {
                                "resource_id": "infores:openpredict",
                                "resource_role": "primary_knowledge_source",
                            },
                            {
                                "resource_id": "infores:cohd",
                                "resource_role": "supporting_data_source",
                            },
                        ],
                        "attributes": [
                            {
                                "description": "model_id",
                                "attribute_type_id": "EDAM:data_1048",
                                "value": "openpredict_baseline",
                            },
                            {
                                "attribute_type_id": "biolink:agent_type",
                                "value": "computational_model",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "biolink:knowledge_level",
                                "value": "prediction",
                                "attribute_source": "infores:openpredict",
                            },
                        ],
                    },
                    "e2": {
                        "subject": "DRUGBANK:DB00177",
                        "object": "MONDO:0001134",
                        "predicate": "biolink:treats",
                        "sources": [
                            {
                                "resource_id": "infores:openpredict",
                                "resource_role": "primary_knowledge_source",
                            },
                            {
                                "resource_id": "infores:cohd",
                                "resource_role": "supporting_data_source",
                            },
                        ],
                        "attributes": [
                            {
                                "description": "model_id",
                                "attribute_type_id": "EDAM:data_1048",
                                "value": "openpredict_baseline",
                            },
                            {
                                "attribute_type_id": "biolink:agent_type",
                                "value": "computational_model",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "biolink:knowledge_level",
                                "value": "prediction",
                                "attribute_source": "infores:openpredict",
                            },
                        ],
                    },
                    "e3": {
                        "subject": "DRUGBANK:DB00966",
                        "object": "MONDO:0001134",
                        "predicate": "biolink:treats",
                        "sources": [
                            {
                                "resource_id": "infores:openpredict",
                                "resource_role": "primary_knowledge_source",
                            },
                            {
                                "resource_id": "infores:cohd",
                                "resource_role": "supporting_data_source",
                            },
                        ],
                        "attributes": [
                            {
                                "description": "model_id",
                                "attribute_type_id": "EDAM:data_1048",
                                "value": "openpredict_baseline",
                            },
                            {
                                "attribute_type_id": "biolink:agent_type",
                                "value": "computational_model",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "biolink:knowledge_level",
                                "value": "prediction",
                                "attribute_source": "infores:openpredict",
                            },
                        ],
                    },
                    "e4": {
                        "subject": "DRUGBANK:DB00678",
                        "object": "MONDO:0001134",
                        "predicate": "biolink:treats",
                        "sources": [
                            {
                                "resource_id": "infores:openpredict",
                                "resource_role": "primary_knowledge_source",
                            },
                            {
                                "resource_id": "infores:cohd",
                                "resource_role": "supporting_data_source",
                            },
                        ],
                        "attributes": [
                            {
                                "description": "model_id",
                                "attribute_type_id": "EDAM:data_1048",
                                "value": "openpredict_baseline",
                            },
                            {
                                "attribute_type_id": "biolink:agent_type",
                                "value": "computational_model",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "biolink:knowledge_level",
                                "value": "prediction",
                                "attribute_source": "infores:openpredict",
                            },
                        ],
                    },
                },
            },
            "results": [
                {
                    "node_bindings": {
                        "n0": [{"id": "DRUGBANK:DB00275"}],
                        "n1": [{"id": "MONDO:0001134"}],
                    },
                    "analyses": [
                        {
                            "resource_id": "infores:openpredict",
                            "score": "0.8515367495059102",
                            "scoring_method": "Model confidence between 0 and 1",
                            "edge_bindings": {"e01": [{"id": "e0"}]},
                        }
                    ],
                },
                {
                    "node_bindings": {
                        "n0": [{"id": "DRUGBANK:DB00876"}],
                        "n1": [{"id": "MONDO:0001134"}],
                    },
                    "analyses": [
                        {
                            "resource_id": "infores:openpredict",
                            "score": "0.8361819712989409",
                            "scoring_method": "Model confidence between 0 and 1",
                            "edge_bindings": {"e01": [{"id": "e1"}]},
                        }
                    ],
                },
                {
                    "node_bindings": {
                        "n0": [{"id": "DRUGBANK:DB00177"}],
                        "n1": [{"id": "MONDO:0001134"}],
                    },
                    "analyses": [
                        {
                            "resource_id": "infores:openpredict",
                            "score": "0.8154221336665431",
                            "scoring_method": "Model confidence between 0 and 1",
                            "edge_bindings": {"e01": [{"id": "e2"}]},
                        }
                    ],
                },
                {
                    "node_bindings": {
                        "n0": [{"id": "DRUGBANK:DB00966"}],
                        "n1": [{"id": "MONDO:0001134"}],
                    },
                    "analyses": [
                        {
                            "resource_id": "infores:openpredict",
                            "score": "0.7155011411093821",
                            "scoring_method": "Model confidence between 0 and 1",
                            "edge_bindings": {"e01": [{"id": "e3"}]},
                        }
                    ],
                },
                {
                    "node_bindings": {
                        "n0": [{"id": "DRUGBANK:DB00678"}],
                        "n1": [{"id": "MONDO:0001134"}],
                    },
                    "analyses": [
                        {
                            "resource_id": "infores:openpredict",
                            "score": "0.682246949249408",
                            "scoring_method": "Model confidence between 0 and 1",
                            "edge_bindings": {"e01": [{"id": "e4"}]},
                        }
                    ],
                },
            ],
        },
        "query_options": {},
        "reasoner_id": "infores:openpredict",
        "schema_version": "1.4.0",
        "biolink_version": "3.1.0",
        "status": "Success",
    }

    expected_output = {
        "message": {
            "query_graph": {
                "nodes": {
                    "n0": {
                        "categories": ["biolink:Drug"],
                        "is_set": False,
                        "constraints": [],
                    },
                    "n1": {
                        "ids": ["MONDO:0001134"],
                        "categories": ["biolink:Disease"],
                        "is_set": False,
                        "constraints": [],
                    },
                },
                "edges": {
                    "e01": {
                        "subject": "n0",
                        "object": "n1",
                        "predicates": ["biolink:treats"],
                        "attribute_constraints": [],
                        "qualifier_constraints": [],
                    }
                },
            },
            "knowledge_graph": {
                "nodes": {
                    "PUBCHEM.COMPOUND:130881": {
                        "categories": [
                            "biolink:ChemicalEntityOrProteinOrPolypeptide",
                            "biolink:ChemicalEntityOrGeneOrGeneProduct",
                            "biolink:OntologyClass",
                            "biolink:ChemicalEntity",
                            "biolink:NamedThing",
                            "biolink:ChemicalOrDrugOrTreatment",
                            "biolink:SmallMolecule",
                            "biolink:PhysicalEssence",
                            "biolink:MolecularMixture",
                            "biolink:PhysicalEssenceOrOccurrent",
                            "biolink:Entity",
                            "biolink:MolecularEntity",
                            "biolink:ChemicalMixture",
                            "biolink:Drug",
                        ],
                        "name": "Olmesartan medoxomil",
                        "attributes": [
                            {
                                "attribute_type_id": "biolink:same_as",
                                "value": [
                                    "PUBCHEM.COMPOUND:130881",
                                    "CHEMBL.COMPOUND:CHEMBL1200692",
                                    "UNII:6M97XTV3HD",
                                    "CHEBI:31932",
                                    "MESH:D000068557",
                                    "CAS:144689-63-4",
                                    "DrugCentral:1985",
                                    "GTOPDB:591",
                                    "HMDB:HMDB0255956",
                                    "INCHIKEY:UQGKUQLKSCSZGY-UHFFFAOYSA-N",
                                    "UMLS:C0386393",
                                    "RXCUI:118463",
                                    "PUBCHEM.COMPOUND:158781",
                                    "CHEMBL.COMPOUND:CHEMBL1516",
                                    "UNII:8W1IQP3U10",
                                    "CHEBI:48416",
                                    "DRUGBANK:DB00275",
                                    "MESH:C437965",
                                    "CAS:144689-24-7",
                                    "HMDB:HMDB0014420",
                                    "INCHIKEY:VTRAEEWXHOVJFV-UHFFFAOYSA-N",
                                    "UMLS:C1098320",
                                    "RXCUI:321064",
                                    "RXCUI:327503",
                                    "UMLS:C1122245",
                                    "RXCUI:349373",
                                    "UMLS:C1164941",
                                    "RXCUI:349401",
                                    "UMLS:C1164973",
                                    "RXCUI:349405",
                                    "UMLS:C1164978",
                                    "RXCUI:352199",
                                    "UMLS:C1169816",
                                    "RXCUI:352200",
                                    "UMLS:C1169817",
                                    "RXCUI:352201",
                                    "UMLS:C1169818",
                                    "RXCUI:358775",
                                    "UMLS:C1176912",
                                    "RXCUI:359114",
                                    "UMLS:C1177272",
                                    "RXCUI:359115",
                                    "UMLS:C1177273",
                                    "RXCUI:369419",
                                    "UMLS:C1243426",
                                    "RXCUI:378991",
                                    "UMLS:C1253369",
                                    "RXCUI:401971",
                                    "UMLS:C1319673",
                                    "RXCUI:402407",
                                    "UMLS:C1321716",
                                    "RXCUI:404880",
                                    "UMLS:C1330085",
                                    "RXCUI:406041",
                                    "UMLS:C1331274",
                                    "RXCUI:575926",
                                    "UMLS:C1593629",
                                    "RXCUI:575927",
                                    "UMLS:C1593630",
                                    "RXCUI:575928",
                                    "UMLS:C1593631",
                                    "RXCUI:730860",
                                    "UMLS:C1965442",
                                    "RXCUI:730862",
                                    "UMLS:C1966103",
                                    "RXCUI:744622",
                                    "UMLS:C1967521",
                                    "RXCUI:744623",
                                    "UMLS:C1967522",
                                    "RXCUI:744626",
                                    "UMLS:C1967524",
                                    "RXCUI:744630",
                                    "UMLS:C1967527",
                                    "RXCUI:744634",
                                    "UMLS:C1967530",
                                    "RXCUI:847040",
                                    "UMLS:C2683431",
                                    "RXCUI:847053",
                                    "UMLS:C2683439",
                                    "RXCUI:847058",
                                    "UMLS:C2683443",
                                    "RXCUI:847059",
                                    "UMLS:C2683444",
                                    "RXCUI:1159559",
                                    "UMLS:C3213945",
                                    "RXCUI:1159560",
                                    "UMLS:C3213946",
                                    "RXCUI:1166087",
                                    "UMLS:C3220320",
                                    "RXCUI:1166088",
                                    "UMLS:C3220321",
                                    "RXCUI:1170817",
                                    "UMLS:C3224933",
                                    "RXCUI:1170818",
                                    "UMLS:C3224934",
                                    "RXCUI:1170823",
                                    "UMLS:C3224939",
                                    "RXCUI:1171463",
                                    "UMLS:C3225542",
                                    "RXCUI:2646044",
                                    "RXCUI:2647304",
                                    "RXCUI:2648326",
                                    "RXCUI:2655442",
                                    "RXCUI:2656124",
                                    "RXCUI:2657318",
                                    "RXCUI:2660825",
                                    "RXCUI:2663366",
                                ],
                                "value_type_id": "EDAM:data_0006",
                                "original_attribute_name": "equivalent_identifiers",
                            }
                        ],
                    },
                    "MONDO:0001134": {
                        "categories": [
                            "biolink:ThingWithTaxon",
                            "biolink:NamedThing",
                            "biolink:DiseaseOrPhenotypicFeature",
                            "biolink:BiologicalEntity",
                            "biolink:Entity",
                            "biolink:Disease",
                        ],
                        "name": "essential hypertension",
                        "attributes": [
                            {
                                "attribute_type_id": "biolink:same_as",
                                "value": [
                                    "MONDO:0001134",
                                    "DOID:10825",
                                    "OMIM:145500",
                                    "UMLS:C0085580",
                                    "MESH:D000075222",
                                    "MEDDRA:10015488",
                                    "MEDDRA:10015491",
                                    "MEDDRA:10036695",
                                    "MEDDRA:10045866",
                                    "NCIT:C3478",
                                    "SNOMEDCT:59621000",
                                    "ICD9:401",
                                ],
                                "value_type_id": "EDAM:data_0006",
                                "original_attribute_name": "equivalent_identifiers",
                            },
                            {
                                "attribute_type_id": "biolink:has_numeric_value",
                                "value": 83.0,
                                "value_type_id": "EDAM:data_0006",
                                "original_attribute_name": "information_content",
                            },
                        ],
                    },
                    "PUBCHEM.COMPOUND:5281037": {
                        "categories": [
                            "biolink:ChemicalEntityOrProteinOrPolypeptide",
                            "biolink:ChemicalEntityOrGeneOrGeneProduct",
                            "biolink:OntologyClass",
                            "biolink:ChemicalEntity",
                            "biolink:NamedThing",
                            "biolink:ChemicalOrDrugOrTreatment",
                            "biolink:SmallMolecule",
                            "biolink:PhysicalEssence",
                            "biolink:MolecularMixture",
                            "biolink:PhysicalEssenceOrOccurrent",
                            "biolink:Entity",
                            "biolink:MolecularEntity",
                            "biolink:ChemicalMixture",
                            "biolink:Drug",
                        ],
                        "name": "Eprosartan",
                        "attributes": [
                            {
                                "attribute_type_id": "biolink:same_as",
                                "value": [
                                    "PUBCHEM.COMPOUND:5281037",
                                    "CHEMBL.COMPOUND:CHEMBL813",
                                    "UNII:2KH13Z0S0Y",
                                    "CHEBI:4814",
                                    "DRUGBANK:DB00876",
                                    "MESH:C068373",
                                    "CAS:133040-01-4",
                                    "DrugCentral:1037",
                                    "GTOPDB:588",
                                    "HMDB:HMDB0015014",
                                    "KEGG.COMPOUND:C07467",
                                    "INCHIKEY:OROAFUQRIXKEMV-LDADJPATSA-N",
                                    "UMLS:C0287041",
                                    "RXCUI:83515",
                                    "RXCUI:310139",
                                    "UMLS:C0976694",
                                    "RXCUI:310140",
                                    "UMLS:C0976695",
                                    "RXCUI:330329",
                                    "UMLS:C1125964",
                                    "RXCUI:330330",
                                    "UMLS:C1125965",
                                    "RXCUI:374612",
                                    "UMLS:C1248699",
                                    "RXCUI:389185",
                                    "UMLS:C1276893",
                                    "RXCUI:393447",
                                    "UMLS:C1306429",
                                    "RXCUI:1161920",
                                    "UMLS:C3216252",
                                    "RXCUI:1161921",
                                    "UMLS:C3216253",
                                    "UMLS:C0772203",
                                    "RXCUI:236878",
                                ],
                                "value_type_id": "EDAM:data_0006",
                                "original_attribute_name": "equivalent_identifiers",
                            }
                        ],
                    },
                    "PUBCHEM.COMPOUND:60846": {
                        "categories": [
                            "biolink:ChemicalEntityOrProteinOrPolypeptide",
                            "biolink:ChemicalEntityOrGeneOrGeneProduct",
                            "biolink:OntologyClass",
                            "biolink:ChemicalEntity",
                            "biolink:NamedThing",
                            "biolink:ChemicalOrDrugOrTreatment",
                            "biolink:SmallMolecule",
                            "biolink:PhysicalEssence",
                            "biolink:MolecularMixture",
                            "biolink:PhysicalEssenceOrOccurrent",
                            "biolink:Entity",
                            "biolink:MolecularEntity",
                            "biolink:ChemicalMixture",
                            "biolink:Drug",
                        ],
                        "name": "Valsartan",
                        "attributes": [
                            {
                                "attribute_type_id": "biolink:same_as",
                                "value": [
                                    "PUBCHEM.COMPOUND:60846",
                                    "CHEMBL.COMPOUND:CHEMBL1069",
                                    "UNII:80M03YXJ7I",
                                    "CHEBI:9927",
                                    "DRUGBANK:DB00177",
                                    "MESH:D000068756",
                                    "CAS:137862-53-4",
                                    "CAS:137863-60-6",
                                    "DrugCentral:2806",
                                    "GTOPDB:3937",
                                    "HMDB:HMDB0014323",
                                    "INCHIKEY:ACWBQPMHZXGDFX-QFIPXVFZSA-N",
                                    "UMLS:C0216784",
                                    "RXCUI:69749",
                                    "RXCUI:153077",
                                    "UMLS:C0593704",
                                    "RXCUI:199850",
                                    "UMLS:C0693534",
                                    "RXCUI:199919",
                                    "UMLS:C0693630",
                                    "RXCUI:216652",
                                    "UMLS:C0719949",
                                    "RXCUI:316881",
                                    "UMLS:C0991106",
                                    "RXCUI:316882",
                                    "UMLS:C0991107",
                                    "RXCUI:335831",
                                    "UMLS:C1132897",
                                    "RXCUI:349199",
                                    "UMLS:C1164734",
                                    "RXCUI:349200",
                                    "UMLS:C1164735",
                                    "RXCUI:349201",
                                    "UMLS:C1164736",
                                    "RXCUI:349483",
                                    "UMLS:C1165066",
                                    "RXCUI:350561",
                                    "UMLS:C1166306",
                                    "RXCUI:351761",
                                    "UMLS:C1169352",
                                    "RXCUI:351762",
                                    "UMLS:C1169353",
                                    "RXCUI:352001",
                                    "UMLS:C1169614",
                                    "RXCUI:352274",
                                    "UMLS:C1169897",
                                    "RXCUI:368070",
                                    "UMLS:C1242046",
                                    "RXCUI:374279",
                                    "UMLS:C1248357",
                                    "RXCUI:378276",
                                    "UMLS:C1252536",
                                    "RXCUI:565165",
                                    "UMLS:C1597601",
                                    "RXCUI:565166",
                                    "UMLS:C1597602",
                                    "RXCUI:565167",
                                    "UMLS:C1597603",
                                    "RXCUI:575745",
                                    "UMLS:C1593460",
                                    "RXCUI:1163997",
                                    "UMLS:C3218288",
                                    "RXCUI:1164561",
                                    "UMLS:C3218834",
                                    "RXCUI:1171720",
                                    "UMLS:C3225788",
                                    "RXCUI:1171721",
                                    "UMLS:C3225789",
                                    "RXCUI:1656335",
                                    "UMLS:C4034064",
                                    "RXCUI:1656348",
                                    "UMLS:C4034062",
                                    "RXCUI:1656353",
                                    "UMLS:C4034060",
                                    "RXCUI:1996251",
                                    "UMLS:C4542154",
                                    "RXCUI:1996252",
                                    "UMLS:C4542155",
                                    "RXCUI:1996253",
                                    "UMLS:C4542156",
                                    "RXCUI:1996254",
                                    "UMLS:C4542157",
                                ],
                                "value_type_id": "EDAM:data_0006",
                                "original_attribute_name": "equivalent_identifiers",
                            }
                        ],
                    },
                },
                "edges": {
                    "e0": {
                        "subject": "PUBCHEM.COMPOUND:130881",
                        "object": "MONDO:0001134",
                        "predicate": "biolink:treats",
                        "sources": [
                            {
                                "resource_id": "infores:cohd",
                                "resource_role": "supporting_data_source",
                            },
                            {
                                "resource_id": "infores:openpredict",
                                "resource_role": "primary_knowledge_source",
                            },
                        ],
                        "attributes": [
                            {
                                "attribute_type_id": "biolink:knowledge_level",
                                "value": "prediction",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "biolink:agent_type",
                                "value": "computational_model",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "EDAM:data_1048",
                                "value": "openpredict_baseline",
                                "description": "model_id",
                            },
                        ],
                    },
                    "e1": {
                        "subject": "PUBCHEM.COMPOUND:5281037",
                        "object": "MONDO:0001134",
                        "predicate": "biolink:treats",
                        "sources": [
                            {
                                "resource_id": "infores:cohd",
                                "resource_role": "supporting_data_source",
                            },
                            {
                                "resource_id": "infores:openpredict",
                                "resource_role": "primary_knowledge_source",
                            },
                        ],
                        "attributes": [
                            {
                                "attribute_type_id": "biolink:knowledge_level",
                                "value": "prediction",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "biolink:agent_type",
                                "value": "computational_model",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "EDAM:data_1048",
                                "value": "openpredict_baseline",
                                "description": "model_id",
                            },
                        ],
                    },
                    "e2": {
                        "subject": "PUBCHEM.COMPOUND:60846",
                        "object": "MONDO:0001134",
                        "predicate": "biolink:treats",
                        "sources": [
                            {
                                "resource_id": "infores:cohd",
                                "resource_role": "supporting_data_source",
                            },
                            {
                                "resource_id": "infores:openpredict",
                                "resource_role": "primary_knowledge_source",
                            },
                        ],
                        "attributes": [
                            {
                                "attribute_type_id": "biolink:knowledge_level",
                                "value": "prediction",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "biolink:agent_type",
                                "value": "computational_model",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "EDAM:data_1048",
                                "value": "openpredict_baseline",
                                "description": "model_id",
                            },
                        ],
                    },
                    "e3": {
                        "subject": "DRUGBANK:DB00966",
                        "object": "MONDO:0001134",
                        "predicate": "biolink:treats",
                        "sources": [
                            {
                                "resource_id": "infores:cohd",
                                "resource_role": "supporting_data_source",
                            },
                            {
                                "resource_id": "infores:openpredict",
                                "resource_role": "primary_knowledge_source",
                            },
                        ],
                        "attributes": [
                            {
                                "attribute_type_id": "biolink:knowledge_level",
                                "value": "prediction",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "biolink:agent_type",
                                "value": "computational_model",
                                "attribute_source": "infores:openpredict",
                            },
                            {
                                "attribute_type_id": "EDAM:data_1048",
                                "value": "openpredict_baseline",
                                "description": "model_id",
                            },
                        ],
                    },
                },
            },
            "results": [
                {
                    "node_bindings": {
                        "n0": [
                            {
                                "id": "PUBCHEM.COMPOUND:130881",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 100.0,
                                        "value_type_id": "EDAM:data_0006",
                                        "original_attribute_name": "information_content",
                                    }
                                ],
                            }
                        ],
                        "n1": [
                            {
                                "id": "MONDO:0001134",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 83.0,
                                        "value_type_id": "EDAM:data_0006",
                                        "original_attribute_name": "information_content",
                                    }
                                ],
                            }
                        ],
                    },
                    "analyses": [
                        {
                            "resource_id": "infores:openpredict",
                            "edge_bindings": {"e01": [{"id": "e0"}]},
                            "score": 0.8515367495059102,
                            "scoring_method": "Model confidence between 0 and 1",
                        }
                    ],
                },
                {
                    "node_bindings": {
                        "n0": [
                            {
                                "id": "PUBCHEM.COMPOUND:5281037",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 92.7,
                                        "value_type_id": "EDAM:data_0006",
                                        "original_attribute_name": "information_content",
                                    }
                                ],
                            }
                        ],
                        "n1": [
                            {
                                "id": "MONDO:0001134",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 83.0,
                                        "value_type_id": "EDAM:data_0006",
                                        "original_attribute_name": "information_content",
                                    }
                                ],
                            }
                        ],
                    },
                    "analyses": [
                        {
                            "resource_id": "infores:openpredict",
                            "edge_bindings": {"e01": [{"id": "e1"}]},
                            "score": 0.8361819712989409,
                            "scoring_method": "Model confidence between 0 and 1",
                        }
                    ],
                },
                {
                    "node_bindings": {
                        "n0": [
                            {
                                "id": "PUBCHEM.COMPOUND:60846",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 92.7,
                                        "value_type_id": "EDAM:data_0006",
                                        "original_attribute_name": "information_content",
                                    }
                                ],
                            }
                        ],
                        "n1": [
                            {
                                "id": "MONDO:0001134",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 83.0,
                                        "value_type_id": "EDAM:data_0006",
                                        "original_attribute_name": "information_content",
                                    }
                                ],
                            }
                        ],
                    },
                    "analyses": [
                        {
                            "resource_id": "infores:openpredict",
                            "edge_bindings": {"e01": [{"id": "e2"}]},
                            "score": 0.8154221336665431,
                            "scoring_method": "Model confidence between 0 and 1",
                        }
                    ],
                },
                {
                    "node_bindings": {
                        "n0": [
                            {
                                "id": "PUBCHEM.COMPOUND:65999",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 95.4,
                                        "value_type_id": "EDAM:data_0006",
                                        "original_attribute_name": "information_content",
                                    }
                                ],
                            }
                        ],
                        "n1": [
                            {
                                "id": "MONDO:0001134",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 83.0,
                                        "value_type_id": "EDAM:data_0006",
                                        "original_attribute_name": "information_content",
                                    }
                                ],
                            }
                        ],
                    },
                    "analyses": [
                        {
                            "resource_id": "infores:openpredict",
                            "edge_bindings": {"e01": [{"id": "e3"}]},
                            "score": 0.7155011411093821,
                            "scoring_method": "Model confidence between 0 and 1",
                        }
                    ],
                },
                {
                    "node_bindings": {
                        "n0": [
                            {
                                "id": "PUBCHEM.COMPOUND:3961",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 90.8,
                                        "value_type_id": "EDAM:data_0006",
                                        "original_attribute_name": "information_content",
                                    }
                                ],
                            }
                        ],
                        "n1": [
                            {
                                "id": "MONDO:0001134",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 83.0,
                                        "value_type_id": "EDAM:data_0006",
                                        "original_attribute_name": "information_content",
                                    }
                                ],
                            }
                        ],
                    },
                    "analyses": [
                        {
                            "resource_id": "infores:openpredict",
                            "edge_bindings": {"e01": [{"id": "e4"}]},
                            "score": 0.682246949249408,
                            "scoring_method": "Model confidence between 0 and 1",
                        }
                    ],
                },
            ],
        },
        "schema_version": "1.4.0",
        "reasoner_id": "infores:openpredict",
        "biolink_version": "3.1.0",
        "query_options": {},
        "status": "Success",
    }

    url = urllib.parse.urljoin(nodenorm_url, "query")
    response = requests.post(url, json=input_json)
    assert response.ok, f"Could not POST test content to {url}: {response.json()}"
    actual_output = response.json()

    # For this issue, we are primarily interested in the results.
    input_results = input_json["message"]["results"]
    expected_results = expected_output["message"]["results"]
    actual_results = actual_output["message"]["results"]

    assert actual_results == expected_results, f"Did not receive the expected results."
