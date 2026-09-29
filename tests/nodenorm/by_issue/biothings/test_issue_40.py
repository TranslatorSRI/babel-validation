# Test for https://github.com/biothings/NodeNormalizationAPI/issues/40
# The NodeNorm ES loader enumerates the Babel compendia by hand
# (plugins/nodenorm/static.py), and its list has neither Food.txt (new in
# Babel 2026jul22) nor CellLine.txt (present since at least 2025sep1). Any
# identifier whose clique lives only in one of those files comes back null from
# the Elasticsearch-backed NodeNorm while the Redis-backed one resolves it.
import urllib.parse

import pytest
import requests

# CURIE -> (label, Babel type). Food.txt cliques are DrugBank/UNII/CHEBI-led; the
# UMLS-led "Food" cliques live in umls.txt, which *is* loaded, so they would not
# catch this. CellLine.txt cliques are CLO-led.
CURIES = {
    "DRUGBANK:DB10501": ("Apple", "biolink:Food"),
    "DRUGBANK:DB10542": ("Goat milk", "biolink:Food"),
    "DRUGBANK:DB11158": ("Pectin", "biolink:Food"),
    "UNII:14C97E680P": ("Wheat germ oil", "biolink:Food"),
    "CLO:0003684": ("HeLa cell", "biolink:CellLine"),
    "CLO:0003685": ("HeLa 229 cell", "biolink:CellLine"),
}


def _xfail_on_elasticsearch(request, target_info):
    """Strict xfail on the ES-backed targets until the issue is fixed: once the index
    contains these compendia the XPASS will fail the run, and the marker comes out."""
    if target_info.get("NodeNormBackend", "redis") == "elasticsearch":
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason="biothings/NodeNormalizationAPI#40: Food.txt and CellLine.txt are not loaded into NodeNorm ES",
            )
        )


@pytest.mark.parametrize("curie", sorted(CURIES))
def test_compendium_is_loaded(request, target_info, curie):
    _xfail_on_elasticsearch(request, target_info)
    label, expected_type = CURIES[curie]
    url = urllib.parse.urljoin(target_info["NodeNormURL"], "get_normalized_nodes")
    response = requests.post(url, json={"curies": [curie], "conflate": False})
    assert (
        response.ok
    ), f"POST {url} returned HTTP {response.status_code}: {response.text[:500]}"
    node = response.json().get(curie)
    assert node is not None, f"{curie} ({label!r}) is not normalizable on {url}"
    types = node.get("type", [])
    assert (
        types and types[0] == expected_type
    ), f"{curie} ({label!r}) should be a {expected_type}, got {types[:1]!r}"
