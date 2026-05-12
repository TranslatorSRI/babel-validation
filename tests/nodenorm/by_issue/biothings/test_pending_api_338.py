# Test for https://github.com/biothings/pending.api/issues/338
# NodeNorm returns null for NCBITaxon:2 when queried alongside MESH:C029371,
# but returns it correctly alongside MESH:D008795. The bug triggers only when
# the two CURIEs are in the same request; each CURIE succeeds on its own.
import urllib.parse

import pytest
import requests

TRIGGERING_PAIR = ["MESH:C029371", "NCBITaxon:2"]
WORKING_PAIR = ["MESH:D008795", "NCBITaxon:2"]
PARAMS = {"conflate": True, "description": False, "drug_chemical_conflate": False}


def _post(nodenorm_url, curies):
    url = urllib.parse.urljoin(nodenorm_url, "get_normalized_nodes")
    return requests.post(url, json={"curies": curies, **PARAMS})


def _assert_ok(response, nodenorm_url, curies):
    url = urllib.parse.urljoin(nodenorm_url, "get_normalized_nodes")
    assert response.ok, (
        f"POST {url} returned HTTP {response.status_code} for {curies}: "
        f"{response.text[:500]}"
    )
    result = response.json()
    assert isinstance(result, dict), (
        f"Expected a dict response, got {type(result).__name__}: {str(result)[:500]}"
    )
    null_curies = [c for c in curies if result.get(c) is None]
    assert not null_curies, f"CURIEs returned as null: {null_curies}"


def test_working_pair(target_info):
    """MESH:D008795 and NCBITaxon:2 together should both be non-null (positive control)."""
    nodenorm_url = target_info["NodeNormURL"]
    response = _post(nodenorm_url, WORKING_PAIR)
    _assert_ok(response, nodenorm_url, WORKING_PAIR)


@pytest.mark.xfail(strict=True, reason="MESH:C029371 alongside NCBITaxon:2 causes NCBITaxon:2 to return null (biothings/pending.api#338)")
def test_triggering_pair(target_info):
    """MESH:C029371 alongside NCBITaxon:2 causes NCBITaxon:2 to return null."""
    nodenorm_url = target_info["NodeNormURL"]
    response = _post(nodenorm_url, TRIGGERING_PAIR)
    _assert_ok(response, nodenorm_url, TRIGGERING_PAIR)


@pytest.mark.parametrize("curie", sorted(set(TRIGGERING_PAIR + WORKING_PAIR)))
def test_individual_curie(target_info, curie):
    """Each CURIE should succeed when queried on its own."""
    nodenorm_url = target_info["NodeNormURL"]
    response = _post(nodenorm_url, [curie])
    _assert_ok(response, nodenorm_url, [curie])
