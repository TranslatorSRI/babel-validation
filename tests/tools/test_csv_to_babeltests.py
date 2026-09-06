"""Unit tests for the csv-to-babeltests CLI helpers.

These exercise the pure-function parts of the tool — CSV parsing, block
construction, YAML emission, and round-trip parsing through the same regex
+ yaml.safe_load that the GitHub-issue test discovery uses. No network.
"""

import re
from pathlib import Path

import pytest
import yaml

from src.babel_validation.tools.csv_to_babeltests import (
    BlockEntry,
    build_blocks,
    emit_yaml,
    parse_yaml_blocks,
    read_csv,
)

# Path to the committed CSV fixture used by the data-asset tests.
FIXTURE_CSV = Path(__file__).parent.parent / "data" / "csv_to_babeltests_fixture.csv"


pytestmark = pytest.mark.unit


# Same regex as src/babel_validation/sources/github/github_issues_test_cases.py
GITHUB_YAML_PATTERN = re.compile(r"```yaml\s+babel_tests:\s+.*?\s+```", re.DOTALL)


def _parse_emitted(yaml_text: str) -> dict:
    """Run emit_yaml() output through the GitHub-issue parser path."""
    match = GITHUB_YAML_PATTERN.search(yaml_text)
    assert match is not None, f"emitted YAML didn't match the issue regex:\n{yaml_text}"
    return yaml.safe_load(
        match.group(0).removeprefix("```yaml").removesuffix("```")
    )


# --- read_csv --------------------------------------------------------------

def test_read_csv_basic(tmp_path: Path):
    p = tmp_path / "in.csv"
    p.write_text("CURIE,Label\nCHEBI:15365,aspirin\nMONDO:1,asthma\n", encoding="utf-8")
    rows = read_csv(p)
    assert rows == [
        {"CURIE": "CHEBI:15365", "Label": "aspirin"},
        {"CURIE": "MONDO:1", "Label": "asthma"},
    ]


def test_read_csv_strips_bom(tmp_path: Path):
    p = tmp_path / "in.csv"
    p.write_bytes("﻿CURIE,Label\nCHEBI:1,foo\n".encode("utf-8"))
    rows = read_csv(p)
    assert rows[0]["CURIE"] == "CHEBI:1"


def test_read_csv_handles_quoted_field_with_comma(tmp_path: Path):
    p = tmp_path / "in.csv"
    p.write_text(
        'CURIE,"Long, Name"\nCHEBI:1,"foo, bar"\n', encoding="utf-8"
    )
    rows = read_csv(p)
    assert rows[0] == {"CURIE": "CHEBI:1", "Long, Name": "foo, bar"}


# --- build_blocks ----------------------------------------------------------

ROWS = [
    {"OutputID": "CHEBI:15365", "Label": "aspirin",   "Type": "biolink:SmallMolecule", "Equiv": "PUBCHEM.COMPOUND:1"},
    {"OutputID": "MONDO:0005015", "Label": "diabetes", "Type": "biolink:Disease",       "Equiv": ""},
    {"OutputID": "",              "Label": "missing",  "Type": "",                       "Equiv": ""},
    {"OutputID": "CHEBI:15365", "Label": "aspirin",   "Type": "biolink:SmallMolecule", "Equiv": "PUBCHEM.COMPOUND:1"},  # dup
]


def test_build_blocks_haslabel_only():
    blocks, warnings = build_blocks(
        ROWS,
        curie_column="OutputID", label_column="Label",
        type_column=None, equivalent_curie_column=None,
        emit_resolves=False, dedupe=False, skip_empty=True,
    )
    assert set(blocks) == {"HasLabel"}
    assert [e.param_set for e in blocks["HasLabel"]] == [
        ["CHEBI:15365", "aspirin"],
        ["MONDO:0005015", "diabetes"],
        ["CHEBI:15365", "aspirin"],   # dup kept (dedupe=False)
    ]
    # row 4 (offset 2 → row index 4) was empty CURIE.
    assert any("row 4" in w and "OutputID" in w for w in warnings)


def test_build_blocks_dedupe_drops_duplicate_param_sets():
    blocks, _ = build_blocks(
        ROWS,
        curie_column="OutputID", label_column="Label",
        type_column=None, equivalent_curie_column=None,
        emit_resolves=False, dedupe=True, skip_empty=True,
    )
    assert [e.param_set for e in blocks["HasLabel"]] == [
        ["CHEBI:15365", "aspirin"],
        ["MONDO:0005015", "diabetes"],
    ]


def test_build_blocks_multiple_assertions():
    blocks, _ = build_blocks(
        ROWS,
        curie_column="OutputID", label_column="Label",
        type_column="Type", equivalent_curie_column="Equiv",
        emit_resolves=True, dedupe=True, skip_empty=True,
    )
    # All four assertion blocks should be present.
    assert set(blocks) == {"HasLabel", "ResolvesWithType", "ResolvesWith", "Resolves"}
    # ResolvesWithType places the Biolink type first.
    rwt = [e.param_set for e in blocks["ResolvesWithType"]]
    assert rwt == [
        ["biolink:SmallMolecule", "CHEBI:15365"],
        ["biolink:Disease", "MONDO:0005015"],
    ]
    # ResolvesWith only fires when Equiv is non-empty.
    rw = [e.param_set for e in blocks["ResolvesWith"]]
    assert rw == [["CHEBI:15365", "PUBCHEM.COMPOUND:1"]]


def test_build_blocks_row_indices_match_spreadsheet_rows():
    """row_idx should be 1-based with the header at row 1 — matches spreadsheet UIs."""
    blocks, _ = build_blocks(
        ROWS,
        curie_column="OutputID", label_column="Label",
        type_column=None, equivalent_curie_column=None,
        emit_resolves=False, dedupe=False, skip_empty=True,
    )
    indices = [e.row_idx for e in blocks["HasLabel"]]
    # ROWS[0] → row 2, ROWS[1] → row 3, ROWS[3] → row 5 (ROWS[2] was empty).
    assert indices == [2, 3, 5]


# --- emit_yaml -------------------------------------------------------------

def test_emit_yaml_round_trips_through_github_parser():
    blocks = {
        "HasLabel": [
            BlockEntry(2, ["CHEBI:15365", "aspirin"]),
            BlockEntry(3, ["MONDO:0005015", "type 2 diabetes mellitus"]),
        ],
        "ResolvesWithType": [
            BlockEntry(2, ["biolink:SmallMolecule", "CHEBI:15365"]),
        ],
    }
    out = emit_yaml(blocks, fence=True, header=None)
    parsed = _parse_emitted(out)
    assert list(parsed["babel_tests"].keys()) == ["HasLabel", "ResolvesWithType"]
    assert parsed["babel_tests"]["HasLabel"] == [
        ["CHEBI:15365", "aspirin"],
        ["MONDO:0005015", "type 2 diabetes mellitus"],
    ]
    assert parsed["babel_tests"]["ResolvesWithType"] == [
        ["biolink:SmallMolecule", "CHEBI:15365"],
    ]


def test_emit_yaml_with_special_characters():
    """Labels with apostrophes, commas, brackets must round-trip."""
    blocks = {
        "HasLabel": [
            BlockEntry(2, ["DRUGBANK:DB00001", "Adenosine 5'-phosphosulfate"]),
            BlockEntry(3, ["CHEBI:1", "foo, bar [baz]"]),
            BlockEntry(4, ["CHEBI:2", ""]),  # empty label edge case
        ],
    }
    out = emit_yaml(blocks)
    parsed = _parse_emitted(out)
    assert parsed["babel_tests"]["HasLabel"] == [
        ["DRUGBANK:DB00001", "Adenosine 5'-phosphosulfate"],
        ["CHEBI:1", "foo, bar [baz]"],
        ["CHEBI:2", ""],
    ]


def test_emit_yaml_no_fence():
    blocks = {"Resolves": [BlockEntry(2, ["CHEBI:15365"])]}
    out = emit_yaml(blocks, fence=False)
    assert "```" not in out
    assert "babel_tests:" in out
    # Without the fence the GitHub parser regex shouldn't find a match.
    assert GITHUB_YAML_PATTERN.search(out) is None


def test_emit_yaml_with_header_comment():
    blocks = {"Resolves": [BlockEntry(2, ["CHEBI:15365"])]}
    out = emit_yaml(blocks, header="from data/test-assets.csv")
    assert out.startswith("# from data/test-assets.csv\n")
    # Header doesn't break the round-trip.
    parsed = _parse_emitted(out)
    # Single-element param_sets are emitted as bare strings (matching the
    # convention in assertions/nodenorm.py); the GitHub parser later wraps
    # them back into [["CHEBI:15365"]].
    assert parsed["babel_tests"]["Resolves"] == ["CHEBI:15365"]


def test_emit_yaml_single_element_param_sets_emit_as_bare_strings():
    """Single-element param_sets should match the existing YAML examples in
    assertions/nodenorm.py — bare strings, not single-item flow lists."""
    blocks = {"Resolves": [BlockEntry(2, ["CHEBI:15365"]), BlockEntry(3, ["MONDO:1"])]}
    out = emit_yaml(blocks, fence=False)
    # Bare-string form, not single-element flow lists.
    assert "- CHEBI:15365" in out
    assert "- [CHEBI:15365]" not in out


# --- assertion-name compatibility with ASSERTION_HANDLERS ------------------

def test_emitted_assertion_names_match_handler_registry():
    """The names build_blocks emits must each resolve in ASSERTION_HANDLERS."""
    from src.babel_validation.assertions import ASSERTION_HANDLERS
    blocks, _ = build_blocks(
        ROWS,
        curie_column="OutputID", label_column="Label",
        type_column="Type", equivalent_curie_column="Equiv",
        emit_resolves=True, dedupe=True, skip_empty=True,
    )
    for assertion in blocks:
        assert assertion.lower() in ASSERTION_HANDLERS, (
            f"build_blocks emitted unknown assertion name {assertion!r}"
        )


# --- CSV data-asset tests (tests/data/csv_to_babeltests_fixture.csv) --------
# Add tricky cases to that file; these tests exercise the full pipeline from
# CSV → build_blocks → emit_yaml → yaml.safe_load without hitting the network.

def test_fixture_csv_exists():
    assert FIXTURE_CSV.is_file(), f"Fixture CSV not found: {FIXTURE_CSV}"


def test_fixture_csv_labels_round_trip():
    """All non-empty Label values survive the full CSV → YAML → parse cycle."""
    rows = read_csv(FIXTURE_CSV)
    blocks, warnings = build_blocks(
        rows,
        curie_column="OutputID", label_column="Label",
        type_column=None, equivalent_curie_column=None,
        emit_resolves=False, dedupe=False, skip_empty=True,
    )
    assert "HasLabel" in blocks

    out = emit_yaml(blocks, fence=True)
    parsed = _parse_emitted(out)
    label_pairs = parsed["babel_tests"]["HasLabel"]

    # Every row with a non-empty OutputID and non-empty Label must appear.
    expected = [
        (r["OutputID"].strip(), r["Label"].strip())
        for r in rows
        if r["OutputID"].strip() and r["Label"].strip()
    ]
    actual = [(p[0], p[1]) for p in label_pairs]
    assert actual == expected, "Label round-trip mismatch"


def test_fixture_csv_tricky_labels():
    """Labels that contain commas, apostrophes, and brackets must survive intact."""
    rows = read_csv(FIXTURE_CSV)
    blocks, _ = build_blocks(
        rows,
        curie_column="OutputID", label_column="Label",
        type_column=None, equivalent_curie_column=None,
        emit_resolves=False, dedupe=False, skip_empty=True,
    )
    out = emit_yaml(blocks, fence=True)
    parsed = _parse_emitted(out)
    pairs = {p[0]: p[1] for p in parsed["babel_tests"]["HasLabel"]}

    assert pairs["CHEBI:27732"] == "caffeine, anhydrous"          # comma
    assert pairs["DRUGBANK:DB00001"] == "Adenosine 5'-phosphosulfate"  # apostrophe
    assert pairs["CHEBI:1"] == "foo [bar] (baz)"                  # brackets + parens


def test_fixture_csv_empty_curie_produces_warning():
    """A row with an empty OutputID must be skipped and produce a warning."""
    rows = read_csv(FIXTURE_CSV)
    _, warnings = build_blocks(
        rows,
        curie_column="OutputID", label_column="Label",
        type_column=None, equivalent_curie_column=None,
        emit_resolves=False, dedupe=False, skip_empty=True,
    )
    assert any("empty" in w and "OutputID" in w for w in warnings), (
        f"Expected a warning about empty OutputID; got: {warnings}"
    )


def test_fixture_csv_dedupe_removes_duplicate_row():
    """The fixture has one exact duplicate row; --dedupe should drop it."""
    rows = read_csv(FIXTURE_CSV)
    blocks_keep, _ = build_blocks(
        rows,
        curie_column="OutputID", label_column="Label",
        type_column=None, equivalent_curie_column=None,
        emit_resolves=False, dedupe=False, skip_empty=True,
    )
    blocks_dedup, _ = build_blocks(
        rows,
        curie_column="OutputID", label_column="Label",
        type_column=None, equivalent_curie_column=None,
        emit_resolves=False, dedupe=True, skip_empty=True,
    )
    # With dedupe=True there should be exactly one fewer HasLabel entry.
    assert len(blocks_dedup["HasLabel"]) == len(blocks_keep["HasLabel"]) - 1


def test_fixture_csv_skip_empty_type_suppresses_resolveswithtype():
    """Rows with an empty Type column must not produce ResolvesWithType entries."""
    rows = read_csv(FIXTURE_CSV)
    blocks, _ = build_blocks(
        rows,
        curie_column="OutputID", label_column=None,
        type_column="Type", equivalent_curie_column=None,
        emit_resolves=False, dedupe=False, skip_empty=True,
    )
    rwt_curies = [e.param_set[1] for e in blocks.get("ResolvesWithType", [])]
    # CHEBI:17968 has no Type value in the fixture; it must not appear.
    assert "CHEBI:17968" not in rwt_curies


# --- parse_yaml_blocks -------------------------------------------------------

def test_parse_yaml_blocks_roundtrip(tmp_path: Path):
    """parse_yaml_blocks ∘ emit_yaml should be idempotent."""
    blocks_in = {
        "HasLabel": [
            BlockEntry(1, ["CHEBI:15365", "aspirin"]),
            BlockEntry(2, ["MONDO:0005015", "type 2 diabetes mellitus"]),
        ],
        "ResolvesWithType": [
            BlockEntry(1, ["biolink:SmallMolecule", "CHEBI:15365"]),
        ],
        "Resolves": [
            BlockEntry(1, ["HGNC:11998"]),
        ],
    }
    yaml_text = emit_yaml(blocks_in, fence=False)
    p = tmp_path / "block.yaml"
    p.write_text(yaml_text, encoding="utf-8")

    blocks_out = parse_yaml_blocks(p)
    assert set(blocks_out) == set(blocks_in)
    for assertion in blocks_in:
        in_sets = [e.param_set for e in blocks_in[assertion]]
        out_sets = [e.param_set for e in blocks_out[assertion]]
        assert out_sets == in_sets, f"param_sets differ for {assertion}"


def test_parse_yaml_blocks_synthetic_row_indices(tmp_path: Path):
    """Row indices assigned by parse_yaml_blocks should be 1-based per assertion."""
    yaml_text = (
        "babel_tests:\n"
        "  HasLabel:\n"
        "  - [CHEBI:15365, aspirin]\n"
        "  - [MONDO:1, asthma]\n"
    )
    p = tmp_path / "block.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    blocks = parse_yaml_blocks(p)
    assert [e.row_idx for e in blocks["HasLabel"]] == [1, 2]


def test_parse_yaml_blocks_single_element_entries(tmp_path: Path):
    """Bare-string entries (Resolves: - CHEBI:15365) must parse to 1-element param_sets."""
    yaml_text = (
        "babel_tests:\n"
        "  Resolves:\n"
        "  - CHEBI:15365\n"
        "  - MONDO:1\n"
    )
    p = tmp_path / "block.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    blocks = parse_yaml_blocks(p)
    assert [e.param_set for e in blocks["Resolves"]] == [["CHEBI:15365"], ["MONDO:1"]]


def test_parse_yaml_blocks_missing_key_raises(tmp_path: Path):
    """A YAML file without a babel_tests: key must raise ClickException."""
    import click
    p = tmp_path / "bad.yaml"
    p.write_text("some_other_key:\n  - foo\n", encoding="utf-8")
    with pytest.raises(click.ClickException, match="babel_tests"):
        parse_yaml_blocks(p)


def test_parse_yaml_blocks_tricky_labels(tmp_path: Path):
    """Labels that were tricky in CSV (commas, apostrophes, brackets) must parse cleanly."""
    yaml_text = emit_yaml(
        {
            "HasLabel": [
                BlockEntry(1, ["CHEBI:27732", "caffeine, anhydrous"]),
                BlockEntry(2, ["DRUGBANK:DB00001", "Adenosine 5'-phosphosulfate"]),
                BlockEntry(3, ["CHEBI:1", "foo [bar] (baz)"]),
            ]
        },
        fence=False,
    )
    p = tmp_path / "block.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    blocks = parse_yaml_blocks(p)
    pairs = {e.param_set[0]: e.param_set[1] for e in blocks["HasLabel"]}
    assert pairs["CHEBI:27732"] == "caffeine, anhydrous"
    assert pairs["DRUGBANK:DB00001"] == "Adenosine 5'-phosphosulfate"
    assert pairs["CHEBI:1"] == "foo [bar] (baz)"
