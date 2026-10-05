"""
Check that each NodeNorm deployment answers its endpoints the way its OpenAPI document says.

NodeNorm Redis and NodeNorm ES are meant to be interchangeable, and these tests hold each
deployment to the response shapes clients were written against. They were added for three
discrepancies found on NodeNorm ES (biothings/NodeNormalizationAPI#42): /get_allowed_conflations
returned HTTP 500, POST /get_setid returned an index-keyed object instead of a list, and
/get_semantic_types lower-cased every Biolink class. Those three are strict xfails on the
Elasticsearch targets until that PR deploys; the unexpected pass is the signal to drop the markers.
"""

import re
import urllib.parse

import pytest
import requests

from tests._service_helpers import openapi_url, truncated_repr

NODENORM_ES_PR = "biothings/NodeNormalizationAPI#42"


def xfail_on_elasticsearch_until_pr_42(request, target_info, what):
    if target_info.get("NodeNormBackend", "redis") == "elasticsearch":
        request.node.add_marker(
            pytest.mark.xfail(strict=True, reason=f"{NODENORM_ES_PR}: {what}")
        )


def test_get_allowed_conflations(request, target_info):
    xfail_on_elasticsearch_until_pr_42(
        request, target_info, "/get_allowed_conflations returns HTTP 500"
    )

    url = urllib.parse.urljoin(target_info["NodeNormURL"], "get_allowed_conflations")
    response = requests.get(url)
    assert response.ok, f"Could not GET {url}: {response}"

    body = response.json()
    assert isinstance(body, dict) and isinstance(
        body.get("conflations"), list
    ), f"{url} should return an object with a 'conflations' list, got {truncated_repr(body)}"
    assert {"GeneProtein", "DrugChemical"} <= set(body["conflations"]), truncated_repr(
        body
    )


def test_get_semantic_types_are_biolink_classes(request, target_info):
    xfail_on_elasticsearch_until_pr_42(
        request, target_info, "/get_semantic_types lower-cases every class"
    )

    url = urllib.parse.urljoin(target_info["NodeNormURL"], "get_semantic_types")
    response = requests.get(url)
    assert response.ok, f"Could not GET {url}: {response}"

    types = response.json()["semantic_types"]["types"]
    assert types, f"{url} returned no semantic types"
    not_classes = [t for t in types if not re.fullmatch(r"biolink:[A-Z][A-Za-z]*", t)]
    assert (
        not not_classes
    ), f"{url} returned types that are not Biolink class CURIEs: {truncated_repr(not_classes)}"


def test_get_setid_post_returns_list(request, target_info):
    xfail_on_elasticsearch_until_pr_42(
        request, target_info, "POST /get_setid returns an index-keyed object"
    )

    url = urllib.parse.urljoin(target_info["NodeNormURL"], "get_setid")
    sets = [
        {"curies": ["MESH:D014867", "NCIT:C34373"]},
        {
            "curies": ["NCIT:C34373", "MESH:D014867", "RUBBISH:1234"],
            "conflations": ["GeneProtein"],
        },
    ]
    response = requests.post(url, json=sets)
    assert response.ok, f"Could not POST to {url}: {response}"

    body = response.json()
    assert isinstance(body, list) and len(body) == len(
        sets
    ), f"POST {url} should return one result per input set as a list, got {truncated_repr(body)}"
    for query, result in zip(sets, body):
        get_response = requests.get(
            url,
            params={
                "curie": query["curies"],
                "conflation": query.get("conflations", []),
            },
        )
        assert get_response.ok, f"Could not GET {get_response.url}: {get_response}"
        assert result["setid"] == get_response.json()["setid"], (
            f"POST and GET disagree on the set ID for {query}: {truncated_repr(result)} vs "
            f"{truncated_repr(get_response.json())}"
        )


def test_every_documented_path_exists(target_info):
    """Every path in the published OpenAPI document is served: anything but a 404 will do."""
    doc_url = openapi_url(target_info, "NodeNormURL", "NodeNormOpenAPIPath")
    response = requests.get(doc_url)
    assert response.ok, f"Could not GET {doc_url}: {response}"

    missing = {}
    for path in response.json()["paths"]:
        url = urllib.parse.urljoin(target_info["NodeNormURL"], path.lstrip("/"))
        status = requests.get(url).status_code
        if status == 404:
            missing[path] = status
    assert (
        not missing
    ), f"{doc_url} documents paths this deployment does not serve: {missing}"
