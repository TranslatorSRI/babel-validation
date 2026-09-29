# Test for https://github.com/biothings/NodeNormalizationAPI/issues/41
# Babel emits some CURIEs as the clique leader in two compendia (Babel #276,
# #308). Redis NodeNorm keeps whichever compendium loaded last; NodeNorm ES
# merges the two documents so that `type` becomes a list, and the API then
# concatenates the Biolink ancestor lists of both types: `biolink:NamedThing`
# twice, `biolink:Entity` once (only the first copy is removed), and the first
# type sometimes flips category altogether.
#
# The property asserted is that `type` is one well-formed ancestor chain: no
# duplicates, no `biolink:Entity`, and not both of the two Babel types that were
# merged. Which of the two cliques NodeNorm serves is arbitrary on both
# backends, so that is deliberately not pinned.
import urllib.parse

import pytest
import requests

from tests._service_helpers import require_babel_release

# The duplicate leaders below are 2026jul22's; each release rearranges them. Older
# deployments (prod, the ES `test` instance on 2025sep1) are skipped.
BABEL_RELEASE = "2026jul22"

# CURIE -> (label, the two Babel types it leads a clique as, per
# reports/duckdb/duplicate_clique_leaders.tsv for 2026jul22). A well-formed answer
# has exactly one of the pair.
DUPLICATE_LEADERS = {
    "MESH:C469385": (
        "RIOK1 protein, human",
        ("biolink:Protein", "biolink:ChemicalEntity"),
    ),
    "MESH:C000719044": (
        "H3N1 virus",
        ("biolink:OrganismTaxon", "biolink:ChemicalEntity"),
    ),
    "MESH:D018517": (
        "Plant Roots",
        ("biolink:OrganismTaxon", "biolink:AnatomicalEntity"),
    ),
    "MESH:D013171": ("Spores, Bacterial", ("biolink:OrganismTaxon", "biolink:Cell")),
    "MESH:D008551": ("Melena", ("biolink:Disease", "biolink:AnatomicalEntity")),
    "ENSEMBL:YMR209C": ("", ("biolink:Protein", "biolink:Gene")),
}

# A MeSH protein that leads a clique in Protein.txt only: positive control.
SINGLE_LEADER = "MESH:C088986"


def _xfail_on_elasticsearch(request, target_info):
    if target_info.get("NodeNormBackend", "redis") == "elasticsearch":
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason="biothings/NodeNormalizationAPI#41: duplicate clique leaders are merged into a list-typed document",
            )
        )


def _normalize(target_info, curie, **params):
    url = urllib.parse.urljoin(target_info["NodeNormURL"], "get_normalized_nodes")
    response = requests.post(url, json={"curies": [curie], "conflate": False, **params})
    assert (
        response.ok
    ), f"POST {url} returned HTTP {response.status_code}: {response.text[:500]}"
    node = response.json().get(curie)
    assert node is not None, f"{curie} is not normalizable on {url}"
    return node


def _assert_well_formed_types(curie, types):
    assert types, f"{curie} has no types"
    duplicates = sorted({t for t in types if types.count(t) > 1})
    assert not duplicates, f"{curie} lists these types more than once: {duplicates}"
    assert (
        "biolink:Entity" not in types
    ), f"{curie} has biolink:Entity in its types: {types}"


@pytest.mark.parametrize("curie", sorted(DUPLICATE_LEADERS))
def test_one_clique_one_type(request, target_info, curie):
    require_babel_release(target_info, BABEL_RELEASE)
    _xfail_on_elasticsearch(request, target_info)
    label, pair = DUPLICATE_LEADERS[curie]
    types = _normalize(target_info, curie)["type"]
    _assert_well_formed_types(curie, types)
    both = [t for t in pair if t in types]
    assert (
        len(both) < 2
    ), f"{curie} ({label!r}) is typed as both {pair[0]} and {pair[1]}: {types}"


@pytest.mark.parametrize("curie", sorted(DUPLICATE_LEADERS))
def test_individual_types_are_strings(request, target_info, curie):
    """With individual_types=true the merged document's per-identifier type is a list of
    lists on ES, where every other identifier gets a single CURIE string."""
    require_babel_release(target_info, BABEL_RELEASE)
    _xfail_on_elasticsearch(request, target_info)
    node = _normalize(target_info, curie, individual_types=True)
    for eqid in node["equivalent_identifiers"]:
        if "type" in eqid:
            assert isinstance(
                eqid["type"], str
            ), f"{curie}: individual type of {eqid['identifier']} is {eqid['type']!r}, not a string"


def test_single_leader_is_well_formed(target_info):
    """Positive control: a CURIE that leads one clique is fine on every backend."""
    require_babel_release(target_info, BABEL_RELEASE)
    types = _normalize(target_info, SINGLE_LEADER)["type"]
    _assert_well_formed_types(SINGLE_LEADER, types)
    assert types[0] == "biolink:Protein"
