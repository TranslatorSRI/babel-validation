"""Normalize the same CURIEs on two NodeNorm targets and tabulate how the answers differ.

    uv run python -m src.babel_validation.tools.compare_nodenorm dev ci MESH:C469385 CLO:0003684
    uv run python -m src.babel_validation.tools.compare_nodenorm dev ci \\
        --nameres 'string=virus&biolink_type=biolink:OrganismTaxon&only_prefixes=MESH&limit=100'

Targets are section names from tests/targets.ini (or full NodeNorm base URLs). CURIEs come
from the command line, from `--curies-file` (one per line), or from one or more NameRes
`lookup` query strings, which is the quickest way to get a batch of a given type and prefix.

Each CURIE is classified as: same; missing on one side; a different preferred identifier; or
the same identifier with extra types on the right. The last two are the signatures of
biothings/NodeNormalizationAPI#41 and #40 respectively -- see
tests/nodenorm/by_issue/biothings/CLAUDE.md.
"""

import argparse
import collections
import configparser
import sys
import urllib.parse
from pathlib import Path

import requests

TARGETS_INI = Path(__file__).resolve().parents[3] / "tests" / "targets.ini"
NAMERES_LOOKUP = "https://name-resolution-sri.renci.org/lookup"
BATCH = 500


def resolve_target(name: str) -> str:
    if name.startswith("http://") or name.startswith("https://"):
        return name
    config = configparser.ConfigParser()
    config.read(TARGETS_INI)
    if name not in config:
        sys.exit(f"{name!r} is neither a URL nor a section of {TARGETS_INI}")
    return config[name]["NodeNormURL"]


def nameres_curies(query: str) -> list[str]:
    params = dict(urllib.parse.parse_qsl(query))
    params.setdefault("limit", "100")
    response = requests.get(NAMERES_LOOKUP, params=params, timeout=120)
    response.raise_for_status()
    hits = response.json()
    if not isinstance(hits, list):
        sys.exit(f"NameRes did not return a list for {query!r}: {str(hits)[:300]!r}")
    return [hit["curie"] for hit in hits]


def normalize(base_url: str, curies: list[str], conflate: bool) -> dict:
    url = urllib.parse.urljoin(base_url, "get_normalized_nodes")
    results = {}
    for start in range(0, len(curies), BATCH):
        body = {"curies": curies[start : start + BATCH], "conflate": conflate}
        response = requests.post(url, json=body, timeout=300)
        response.raise_for_status()
        results.update(response.json())
    return results


def classify(left: dict | None, right: dict | None) -> str:
    if left is None and right is None:
        return "missing on both"
    if right is None:
        return "missing on right"
    if left is None:
        return "missing on left"
    if left["id"]["identifier"] != right["id"]["identifier"]:
        return "different preferred identifier"
    extra = [t for t in right.get("type", []) if t not in left.get("type", [])]
    if extra:
        leaves = sorted({t.replace("biolink:", "") for t in extra})[:4]
        return "right has extra types: " + ", ".join(leaves)
    if left.get("type") != right.get("type"):
        return "same types, different order"
    return "same"


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("left", help="targets.ini section or NodeNorm URL, e.g. dev")
    parser.add_argument("right", help="targets.ini section or NodeNorm URL, e.g. ci")
    parser.add_argument("curies", nargs="*")
    parser.add_argument("--curies-file", type=Path, help="one CURIE per line")
    parser.add_argument(
        "--nameres",
        action="append",
        default=[],
        metavar="QUERY",
        help="NameRes lookup query string; repeatable",
    )
    parser.add_argument(
        "--conflate",
        action="store_true",
        help="ask for gene/protein conflation (default off)",
    )
    parser.add_argument(
        "--examples", type=int, default=5, help="examples to print per difference class"
    )
    args = parser.parse_args(argv)

    curies = list(dict.fromkeys(args.curies))
    if args.curies_file:
        curies += [
            line.strip()
            for line in args.curies_file.read_text().splitlines()
            if line.strip()
        ]
    for query in args.nameres:
        curies += nameres_curies(query)
    curies = list(dict.fromkeys(curies))
    if not curies:
        sys.exit("no CURIEs given")

    left_url, right_url = resolve_target(args.left), resolve_target(args.right)
    print(
        f"{len(curies)} CURIEs; left={left_url} right={right_url} conflate={args.conflate}",
        file=sys.stderr,
    )
    left = normalize(left_url, curies, args.conflate)
    right = normalize(right_url, curies, args.conflate)

    counts = collections.Counter()
    examples = collections.defaultdict(list)
    for curie in curies:
        kind = classify(left.get(curie), right.get(curie))
        counts[kind] += 1
        if len(examples[kind]) < args.examples:
            examples[kind].append(curie)

    for kind, count in counts.most_common():
        print(f"{count:6d}  {kind}")
    print()
    for kind, curie_list in examples.items():
        if kind == "same":
            continue
        print(f"## {kind}")
        for curie in curie_list:
            l, r = left.get(curie), right.get(curie)
            print(f"   {curie!r}")
            for side, node in (("left ", l), ("right", r)):
                if node is None:
                    print(f"      {side}: null")
                else:
                    print(
                        f"      {side}: {node['id']['identifier']!r} {node['id'].get('label', '')!r} "
                        f"types={len(node.get('type', []))} first={node.get('type', [None])[0]!r}"
                    )


if __name__ == "__main__":
    main()
