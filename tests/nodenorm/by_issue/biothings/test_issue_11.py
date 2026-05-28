# Test for https://github.com/biothings/NodeNormalizationAPI/issues/11
# When querying UMLS:C0106127, CHEMBL.COMPOUND:CHEMBL221542, and
# PUBCHEM.COMPOUND:222284 with drug_chemical_conflate=true, NodeNorm Redis
# returned 146 entries in equivalent_identifiers while NodeNorm ES returned 32.
# The Redis result contained the same identifier (e.g. CAS:76772-70-8) up to
# six times. Regardless of which backend is serving the request, the
# equivalent_identifiers list for each normalized node must not contain
# duplicate identifiers.
import urllib.parse

import pytest
import requests

CURIES = [
    "UMLS:C0106127",
    "CHEMBL.COMPOUND:CHEMBL221542",
    "PUBCHEM.COMPOUND:222284",
]

# Expected number of unique CURIEs in equivalent_identifiers for each setting,
# taken from the issue (17 without conflate on both backends, 32 with conflate
# on ES, and 32 unique on Redis once the duplicates are removed).
EXPECTED_UNIQUE_COUNTS = {False: 17, True: 32}


def _post(nodenorm_url, drug_chemical_conflate):
    url = urllib.parse.urljoin(nodenorm_url, "get_normalized_nodes")
    return requests.post(
        url,
        json={
            "curies": CURIES,
            "conflate": True,
            "drug_chemical_conflate": drug_chemical_conflate,
        },
    )


def _assert_equivalent_identifiers(response, nodenorm_url, drug_chemical_conflate):
    url = urllib.parse.urljoin(nodenorm_url, "get_normalized_nodes")
    assert response.ok, (
        f"POST {url} returned HTTP {response.status_code} for {CURIES} "
        f"(drug_chemical_conflate={drug_chemical_conflate}): {response.text[:500]}"
    )
    result = response.json()
    assert isinstance(result, dict), (
        f"Expected a dict response, got {type(result).__name__}: {str(result)[:500]}"
    )

    expected_unique = EXPECTED_UNIQUE_COUNTS[drug_chemical_conflate]
    for curie in CURIES:
        node = result.get(curie)
        assert node is not None, (
            f"{curie} returned null with drug_chemical_conflate={drug_chemical_conflate}"
        )
        equiv = node.get("equivalent_identifiers", [])
        identifiers = [entry["identifier"] for entry in equiv]
        unique = set(identifiers)
        duplicates = sorted({i for i in identifiers if identifiers.count(i) > 1})
        assert not duplicates, (
            f"{curie} (drug_chemical_conflate={drug_chemical_conflate}) returned "
            f"{len(identifiers)} equivalent_identifiers with {len(duplicates)} duplicated "
            f"identifiers: {duplicates}"
        )
        assert len(unique) == expected_unique, (
            f"{curie} (drug_chemical_conflate={drug_chemical_conflate}) returned "
            f"{len(unique)} unique equivalent_identifiers, expected {expected_unique}"
        )


@pytest.mark.parametrize("drug_chemical_conflate", [False, True])
def test_equivalent_identifiers(target_info, drug_chemical_conflate):
    """equivalent_identifiers must contain each identifier at most once,
    and the unique count must match the values reported in the issue."""
    nodenorm_url = target_info["NodeNormURL"]
    response = _post(nodenorm_url, drug_chemical_conflate=drug_chemical_conflate)
    _assert_equivalent_identifiers(
        response, nodenorm_url, drug_chemical_conflate=drug_chemical_conflate
    )
