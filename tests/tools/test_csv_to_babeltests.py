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
    read_csv,
)


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
