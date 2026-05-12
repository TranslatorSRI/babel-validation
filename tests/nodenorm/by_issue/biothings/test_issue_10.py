# Test for https://github.com/biothings/NodeNormalizationAPI/issues/10
# Querying UNII:2ZM8CX04RZ with drug_chemical_conflate=True causes HTTP 500.
# The same query with drug_chemical_conflate=False succeeds.
import urllib.parse

import pytest
import requests

CURIE = "UNII:2ZM8CX04RZ"


def _post(nodenorm_url, drug_chemical_conflate):
    url = urllib.parse.urljoin(nodenorm_url, "get_normalized_nodes")
    return requests.post(
        url,
        json={"curies": [CURIE], "conflate": True, "drug_chemical_conflate": drug_chemical_conflate},
    )


def _assert_ok(response, nodenorm_url, drug_chemical_conflate):
    url = urllib.parse.urljoin(nodenorm_url, "get_normalized_nodes")
    assert response.ok, (
        f"POST {url} returned HTTP {response.status_code} for {CURIE} "
        f"(drug_chemical_conflate={drug_chemical_conflate}): {response.text[:500]}"
    )
    result = response.json()
    assert isinstance(result, dict), (
        f"Expected a dict response, got {type(result).__name__}: {str(result)[:500]}"
    )
    assert CURIE in result, f"{CURIE} missing from response"


def test_without_drug_chemical_conflate(target_info):
    """UNII:2ZM8CX04RZ should succeed when drug_chemical_conflate=False."""
    response = _post(target_info["NodeNormURL"], drug_chemical_conflate=False)
    _assert_ok(response, target_info["NodeNormURL"], drug_chemical_conflate=False)


def test_with_drug_chemical_conflate(target_info):
    """UNII:2ZM8CX04RZ triggers HTTP 500 when drug_chemical_conflate=True."""
    response = _post(target_info["NodeNormURL"], drug_chemical_conflate=True)
    _assert_ok(response, target_info["NodeNormURL"], drug_chemical_conflate=True)
