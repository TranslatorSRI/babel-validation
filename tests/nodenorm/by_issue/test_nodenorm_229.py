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
            "results": [
                {
                    "node_bindings": {
                        "n0": [
                            {
                                "id": "CHEBI:31932",
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
                                        "value": 83.1,
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
                                "id": "CHEBI:4814",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 92.8,
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
                                        "value": 83.1,
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
                                "id": "CHEBI:9927",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 92.8,
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
                                        "value": 83.1,
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
                                "id": "CHEBI:9434",
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
                                        "value": 83.1,
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
                        "n0": [{
                            "id": "CHEBI:6541",
                            "attributes": [
                                {
                                    "attribute_type_id": "biolink:has_numeric_value",
                                    "value": 90.9,
                                    "value_type_id": "EDAM:data_0006",
                                    "original_attribute_name": "information_content",
                                }
                            ],
                        }],
                        "n1": [
                            {
                                "id": "MONDO:0001134",
                                "attributes": [
                                    {
                                        "attribute_type_id": "biolink:has_numeric_value",
                                        "value": 83.1,
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
