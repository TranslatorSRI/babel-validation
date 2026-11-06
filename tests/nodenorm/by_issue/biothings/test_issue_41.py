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
import pytest

from tests._service_helpers import (
    get_normalized_node,
    require_babel_release,
    truncated_repr,
)

# The duplicate leaders below are 2026jul22's; each release rearranges them. Older
# deployments (prod and test, on 2025sep1) are skipped.
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


def _assert_well_formed_types(curie, types):
    assert (
        isinstance(types, list) and types
    ), f"{curie} has no list of types: {truncated_repr(types)}"
    duplicates = sorted({repr(t) for t in types if types.count(t) > 1})
    assert (
        not duplicates
    ), f"{curie} lists these types more than once: {truncated_repr(duplicates)}"
    assert (
        "biolink:Entity" not in types
    ), f"{curie} has biolink:Entity in its types: {truncated_repr(types)}"


@pytest.mark.parametrize("curie", sorted(DUPLICATE_LEADERS))
def test_one_clique_one_type(request, target_info, curie):
    require_babel_release(target_info, BABEL_RELEASE)
    _xfail_on_elasticsearch(request, target_info)
    label, pair = DUPLICATE_LEADERS[curie]
    types = get_normalized_node(target_info, curie).get("type")
    _assert_well_formed_types(curie, types)
    both = [t for t in pair if t in types]
    assert (
        len(both) < 2
    ), f"{curie} ({label!r}) is typed as both {pair[0]} and {pair[1]}: {truncated_repr(types)}"


@pytest.mark.parametrize("curie", sorted(DUPLICATE_LEADERS))
def test_individual_types_are_strings(request, target_info, curie):
    """With individual_types=true the merged document's per-identifier type is a list of
    lists on ES, where every other identifier gets a single CURIE string."""
    require_babel_release(target_info, BABEL_RELEASE)
    _xfail_on_elasticsearch(request, target_info)
    node = get_normalized_node(target_info, curie, individual_types=True)
    eqids = node.get("equivalent_identifiers")
    assert isinstance(
        eqids, list
    ), f"{curie}: equivalent_identifiers is {truncated_repr(eqids)}"
    typed = [eqid for eqid in eqids if isinstance(eqid, dict) and "type" in eqid]
    # Without this, a backend that ignored individual_types would pass vacuously.
    assert (
        typed
    ), f"{curie}: no equivalent identifier has a type with individual_types=true"
    for eqid in typed:
        assert isinstance(
            eqid["type"], str
        ), f"{curie}: individual type of {truncated_repr(eqid.get('identifier'))} is {truncated_repr(eqid['type'])}, not a string"


def test_single_leader_is_well_formed(target_info):
    """Positive control: a CURIE that leads one clique is fine on every backend."""
    require_babel_release(target_info, BABEL_RELEASE)
    types = get_normalized_node(target_info, SINGLE_LEADER).get("type")
    _assert_well_formed_types(SINGLE_LEADER, types)
    assert types[0] == "biolink:Protein"
