"""csv-to-babeltests
====================

Convert a CSV of (CURIE, label/type/equivalent-CURIE) rows into a YAML
``babel_tests:`` block suitable for pasting into a GitHub issue, optionally
validating each row against a NodeNorm endpoint defined in
``tests/targets.ini``.

The emitted YAML is the same format consumed by
``GitHubIssuesTestCases.get_test_issues_from_issue`` — assertion handlers and
YAML schema are reused, not duplicated.

Run:
    uv run csv-to-babeltests INPUT.csv --curie-column OutputID \\
        --label-column "Expected Result / Suggested Comparator" --target dev
"""

from __future__ import annotations

import configparser
import csv
import io
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import click
import yaml

from src.babel_validation.assertions import ASSERTION_HANDLERS
from src.babel_validation.core.testrow import TestStatus
from src.babel_validation.services.nodenorm import CachedNodeNorm


# --- YAML emission ---------------------------------------------------------

class _FlowList(list):
    """List subclass that yaml.safe_dump emits in inline flow style."""


def _represent_flow_list(dumper, data):
    return dumper.represent_sequence(
        "tag:yaml.org,2002:seq", data, flow_style=True
    )


yaml.SafeDumper.add_representer(_FlowList, _represent_flow_list)


# --- Data structures -------------------------------------------------------

@dataclass
class BlockEntry:
    """One assertion invocation: a param_set with provenance back to a CSV row."""
    row_idx: int           # 1-based; header is row 1, first data row is row 2.
    param_set: list[str]


@dataclass
class ValidationResult:
    assertion: str
    row_idx: int
    param_set: list[str]
    status: TestStatus
    messages: list[str] = field(default_factory=list)


# --- Pure functions (testable without network) -----------------------------

def read_csv(path: Path | str, delimiter: str | None = None) -> list[dict[str, str]]:
    """Read a CSV file (or '-' for stdin) into a list of dict rows.

    If ``delimiter`` is None we let csv.Sniffer guess from the first 4KiB,
    falling back to ',' on failure.
    """
    if str(path) == "-":
        text = sys.stdin.read()
    else:
        text = Path(path).read_text(encoding="utf-8-sig")  # strip any BOM

    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",\t;|").delimiter
        except csv.Error:
            delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return list(reader)


def build_blocks(
    rows: list[dict[str, str]],
    *,
    curie_column: str,
    label_column: str | None,
    type_column: str | None,
    equivalent_curie_column: str | None,
    emit_resolves: bool,
    dedupe: bool,
    skip_empty: bool,
) -> tuple[dict[str, list[BlockEntry]], list[str]]:
    """Turn CSV rows into ``{assertion_name: [BlockEntry, ...]}``.

    Returns ``(blocks, warnings)``. Warnings is a list of human-readable
    strings the caller can dump to stderr (e.g. "row 17: empty OutputID").
    """
    blocks: dict[str, list[BlockEntry]] = defaultdict(list)
    warnings: list[str] = []
    seen: dict[str, set[tuple[str, ...]]] = defaultdict(set)

    def add(assertion: str, param_set: list[str], row_idx: int) -> None:
        key = tuple(param_set)
        if dedupe and key in seen[assertion]:
            return
        seen[assertion].add(key)
        blocks[assertion].append(BlockEntry(row_idx=row_idx, param_set=param_set))

    for offset, row in enumerate(rows):
        row_idx = offset + 2  # match what spreadsheet UIs show: header is row 1.

        curie = (row.get(curie_column) or "").strip()
        if not curie:
            warnings.append(f"row {row_idx}: empty {curie_column!r} — skipping")
            continue

        if label_column is not None:
            label = (row.get(label_column) or "").strip()
            if not label and skip_empty:
                warnings.append(f"row {row_idx}: empty {label_column!r} — skipping HasLabel")
            else:
                add("HasLabel", [curie, label], row_idx)

        if type_column is not None:
            biolink_type = (row.get(type_column) or "").strip()
            if not biolink_type and skip_empty:
                warnings.append(f"row {row_idx}: empty {type_column!r} — skipping ResolvesWithType")
            else:
                add("ResolvesWithType", [biolink_type, curie], row_idx)

        if equivalent_curie_column is not None:
            equiv = (row.get(equivalent_curie_column) or "").strip()
            if not equiv and skip_empty:
                warnings.append(f"row {row_idx}: empty {equivalent_curie_column!r} — skipping ResolvesWith")
            else:
                add("ResolvesWith", [curie, equiv], row_idx)

        if emit_resolves:
            add("Resolves", [curie], row_idx)

    return dict(blocks), warnings


def emit_yaml(
    blocks: dict[str, list[BlockEntry]],
    *,
    fence: bool = True,
    header: str | None = None,
) -> str:
    """Render a ``{assertion_name: [BlockEntry, ...]}`` map as a YAML block.

    Each param_set is emitted as an inline flow list so the output reads like
    the existing examples in ``assertions/nodenorm.py``::

        babel_tests:
          HasLabel:
          - [CHEBI:15365, aspirin]

    A round-trip self-check via ``yaml.safe_load`` ensures we never emit
    something the GitHub-issue parser would reject.
    """
    # Match the convention used in src/babel_validation/assertions/nodenorm.py:
    # single-element param_sets are emitted as bare strings ("- CHEBI:15365"),
    # multi-element ones as inline flow lists ("- [CHEBI:15365, aspirin]").
    # Both parse to the same param_set via the GitHub issue loader.
    data = {
        "babel_tests": {
            assertion: [
                e.param_set[0] if len(e.param_set) == 1 else _FlowList(e.param_set)
                for e in entries
            ]
            for assertion, entries in blocks.items()
        }
    }
    body = yaml.safe_dump(
        data,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10_000,
    )

    # Round-trip self-check; raises if our output isn't loadable.
    yaml.safe_load(body)

    parts: list[str] = []
    if header:
        parts.append(f"# {header}")
    if fence:
        parts.append("```yaml")
    parts.append(body.rstrip())
    if fence:
        parts.append("```")
    return "\n".join(parts) + "\n"


# --- Validation ------------------------------------------------------------

def validate_blocks(
    blocks: dict[str, list[BlockEntry]],
    nodenorm: CachedNodeNorm,
) -> list[ValidationResult]:
    """Run each (assertion, param_set) through the matching ASSERTION_HANDLER.

    Param_sets are evaluated one at a time so each ``TestResult`` can be
    attributed back to its source CSV row. ``CachedNodeNorm`` deduplicates
    network calls per CURIE, so the per-row loop is no slower than batching.
    """
    # Pre-warm the cache with every CURIE we'll need across all blocks.
    all_curies: set[str] = set()
    for assertion, entries in blocks.items():
        handler = ASSERTION_HANDLERS[assertion.lower()]
        for entry in entries:
            all_curies.update(handler.curie_params(entry.param_set))
    if all_curies:
        nodenorm.normalize_curies(list(all_curies))

    results: list[ValidationResult] = []
    for assertion, entries in blocks.items():
        handler = ASSERTION_HANDLERS[assertion.lower()]
        for entry in entries:
            test_results = list(
                handler.test_with_nodenorm(
                    [entry.param_set], nodenorm,
                    label=f"row {entry.row_idx}",
                )
            )
            if test_results and all(r.status == TestStatus.Passed for r in test_results):
                status = TestStatus.Passed
                messages: list[str] = []
            else:
                status = TestStatus.Failed
                messages = [r.message for r in test_results
                            if r.status != TestStatus.Passed] or ["no result"]
            results.append(ValidationResult(
                assertion=assertion,
                row_idx=entry.row_idx,
                param_set=entry.param_set,
                status=status,
                messages=messages,
            ))
    return results


def format_report(
    results: list[ValidationResult],
    target_name: str,
    nodenorm_url: str,
) -> str:
    """Human-readable validation summary, suitable for stderr."""
    by_assertion: dict[str, list[ValidationResult]] = defaultdict(list)
    for r in results:
        by_assertion[r.assertion].append(r)

    lines = [f"Validation against target {target_name!r} ({nodenorm_url}):"]
    for assertion, rows in by_assertion.items():
        passed = sum(1 for r in rows if r.status == TestStatus.Passed)
        failed = sum(1 for r in rows if r.status == TestStatus.Failed)
        lines.append(f"  {assertion}: {passed} passed, {failed} failed.")
        for r in rows:
            if r.status == TestStatus.Failed:
                params_str = ", ".join(r.param_set)
                lines.append(
                    f"    FAIL  row {r.row_idx}  [{params_str}]  →  {r.messages[0]}"
                )
    return "\n".join(lines) + "\n"


# --- targets.ini -----------------------------------------------------------

def _default_targets_ini() -> Path:
    """Locate tests/targets.ini relative to this file's repo."""
    # src/babel_validation/tools/csv_to_babeltests.py → ../../../tests/targets.ini
    return Path(__file__).resolve().parents[3] / "tests" / "targets.ini"


def load_nodenorm_url(target_name: str, targets_ini_path: Path) -> str:
    """Look up ``NodeNormURL`` for ``target_name`` in ``targets_ini_path``."""
    if not targets_ini_path.is_file():
        raise click.ClickException(f"targets.ini not found at {targets_ini_path}")
    cp = configparser.ConfigParser()
    cp.read(targets_ini_path, encoding="utf-8")
    if target_name not in cp:
        raise click.ClickException(
            f"target {target_name!r} not found in {targets_ini_path}; "
            f"available: {', '.join(cp.sections())}"
        )
    section = cp[target_name]
    if "NodeNormURL" not in section:
        raise click.ClickException(
            f"target {target_name!r} in {targets_ini_path} has no NodeNormURL"
        )
    return section["NodeNormURL"]


# --- CLI -------------------------------------------------------------------

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "input_csv",
    type=click.Path(exists=True, dir_okay=False, allow_dash=True, path_type=Path),
)
@click.option(
    "--curie-column", required=True,
    help="Column name containing the primary CURIE.",
)
@click.option(
    "--label-column", default=None,
    help="Column with the expected label → emits a HasLabel block.",
)
@click.option(
    "--type-column", default=None,
    help="Column with a Biolink type (e.g. 'biolink:SmallMolecule') → emits a ResolvesWithType block.",
)
@click.option(
    "--equivalent-curie-column", default=None,
    help="Column with a CURIE that should merge to the same canonical id → emits a ResolvesWith block.",
)
@click.option(
    "--resolves/--no-resolves", "emit_resolves_flag", default=None,
    help=("Force-emit (or suppress) a Resolves block. Default: emit a Resolves "
          "block only when no other assertion column was given."),
)
@click.option("--dedupe", is_flag=True, default=False,
              help="Drop duplicate param_sets within each assertion block.")
@click.option("--skip-empty/--no-skip-empty", default=True,
              help="Skip rows where the assertion column is blank (with a stderr warning).")
@click.option("--delimiter", default=None,
              help="CSV delimiter (default: auto-detect via csv.Sniffer; falls back to comma).")
@click.option("--target", default=None,
              help="Target name from targets.ini to validate against (e.g. dev, prod, ci).")
@click.option(
    "--targets-ini",
    type=click.Path(exists=False, dir_okay=False, path_type=Path),
    default=None,
    help="Override path to targets.ini (default: tests/targets.ini in the repo).",
)
@click.option("--fence/--no-fence", default=True,
              help="Wrap output in ```yaml … ``` Markdown fences (default: on).")
@click.option("--header", default=None,
              help="Optional comment line emitted above the YAML block "
                   "(useful for recording provenance).")
def main(
    input_csv: Path,
    curie_column: str,
    label_column: str | None,
    type_column: str | None,
    equivalent_curie_column: str | None,
    emit_resolves_flag: bool | None,
    dedupe: bool,
    skip_empty: bool,
    delimiter: str | None,
    target: str | None,
    targets_ini: Path | None,
    fence: bool,
    header: str | None,
) -> None:
    """Convert INPUT_CSV into a BabelTests YAML block on stdout."""

    # Default behavior for --resolves: emit Resolves only when the user
    # didn't ask for any of the other assertion blocks.
    if emit_resolves_flag is None:
        emit_resolves = not (label_column or type_column or equivalent_curie_column)
    else:
        emit_resolves = emit_resolves_flag

    rows = read_csv(input_csv, delimiter=delimiter)
    if rows and curie_column not in rows[0]:
        raise click.ClickException(
            f"--curie-column {curie_column!r} not found in CSV header. "
            f"Available columns: {list(rows[0].keys())}"
        )
    for col_name, col_label in [
        (label_column, "--label-column"),
        (type_column, "--type-column"),
        (equivalent_curie_column, "--equivalent-curie-column"),
    ]:
        if col_name and rows and col_name not in rows[0]:
            raise click.ClickException(
                f"{col_label} {col_name!r} not found in CSV header. "
                f"Available columns: {list(rows[0].keys())}"
            )

    blocks, warnings = build_blocks(
        rows,
        curie_column=curie_column,
        label_column=label_column,
        type_column=type_column,
        equivalent_curie_column=equivalent_curie_column,
        emit_resolves=emit_resolves,
        dedupe=dedupe,
        skip_empty=skip_empty,
    )

    if not blocks:
        raise click.ClickException(
            "No assertions to emit — every row was skipped or no assertion "
            "columns were given. Pass --label-column / --type-column / "
            "--equivalent-curie-column, or use --resolves to force a Resolves "
            "block on the CURIE column."
        )

    for w in warnings:
        click.echo(w, err=True)

    yaml_text = emit_yaml(blocks, fence=fence, header=header)
    sys.stdout.write(yaml_text)

    if target:
        ini_path = targets_ini or _default_targets_ini()
        nodenorm_url = load_nodenorm_url(target, ini_path)
        nodenorm = CachedNodeNorm.from_url(nodenorm_url)
        results = validate_blocks(blocks, nodenorm)
        click.echo(format_report(results, target, nodenorm_url), err=True)


if __name__ == "__main__":  # pragma: no cover
    main()
