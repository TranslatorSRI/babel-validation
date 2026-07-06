import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def title(mo):
    mo.md(r"""
    # NameRes Log Analysis

    Analysis of **NameRes** (Name Resolver) query logs from the Solr-backed
    production service. The goal is to characterize how NameRes performs on
    different kinds of free-text `lookup` queries, and to build a **benchmark**
    we can replay against an alternate NameRes implementation backed by
    **ElasticSearch**.

    This mirrors the NodeNorm log analysis notebook, but NameRes queries are
    single free-text strings with filters (rather than lists of CURIEs), and
    each log line reports two latencies: total request time (`took`) and the
    portion spent **waiting for Solr**.

    A typical log line looks like:

    ```
    INFO:api.server:Lookup query to Solr for "SRSF2" (autocomplete=False,
      highlighting=False, offset=0, limit=10, biolink_types=[], only_prefixes=,
      exclude_prefixes=, only_taxa=) took 56.13ms (with 55.58ms waiting for Solr)
    ```
    """)
    return


@app.cell
def imports():
    import json
    import re
    import ast
    from dataclasses import dataclass, field, asdict
    from datetime import datetime
    from pathlib import Path

    import marimo as mo
    import pandas as pd
    import numpy as np
    import altair as alt

    return Path, asdict, ast, dataclass, datetime, json, mo, np, pd, re


@app.cell
def log_path(Path, mo):
    # Path to the raw NameRes log export (a CloudWatch/Log Insights JSON dump).
    # This file is intentionally NOT checked into the repository (see logs/.gitignore).
    LOG_PATH = Path("logs/nameres-log-analytics-results-2026-07-06.json")
    mo.md(f"Reading log file: `{LOG_PATH}`")
    return (LOG_PATH,)


@app.cell(hide_code=True)
def load_section(mo):
    mo.md(r"""
    ## Loading the log file into a dataclass

    Each record in the JSON export wraps a single Solr `lookup` log line. We parse
    each line into a `QueryLogEntry` dataclass capturing the query, its parameters,
    and both latency measurements. Filter fields (`only_prefixes`, `exclude_prefixes`,
    `only_taxa`) are `|`-delimited in the log and normalized here into lists; an empty
    value or the literal `None` becomes an empty list (i.e. no filter).
    """)
    return


@app.cell
def parser(ast, dataclass, datetime, re):
    @dataclass
    class QueryLogEntry:
        """A single NameRes Solr lookup, parsed from one log line."""

        time: datetime
        query: str
        query_length: int
        autocomplete: bool
        highlighting: bool
        offset: int
        limit: int
        biolink_types: list[str]
        only_prefixes: list[str]
        exclude_prefixes: list[str]
        only_taxa: list[str]
        took_ms: float          # total request time
        solr_wait_ms: float     # time spent waiting for Solr
        slow_query: bool        # emitted as a WARNING "SLOW QUERY" line
        pod_name: str = ""
        image_tag: str = ""


    # Matches both the INFO and the WARNING ("SLOW QUERY:") log variants.
    LOOKUP_LINE_RE = re.compile(
        r'Lookup query to Solr for "(?P<query>.*)" '
        r"\(autocomplete=(?P<autocomplete>True|False), "
        r"highlighting=(?P<highlighting>True|False), "
        r"offset=(?P<offset>\d+), limit=(?P<limit>\d+), "
        r"biolink_types=(?P<biolink_types>\[.*?\]), "
        r"only_prefixes=(?P<only_prefixes>.*?), "
        r"exclude_prefixes=(?P<exclude_prefixes>.*?), "
        r"only_taxa=(?P<only_taxa>.*?)\) "
        r"took (?P<took>[\d.]+)ms \(with (?P<solr>[\d.]+)ms waiting for Solr\)"
    )


    def _parse_filter_list(value: str) -> list[str]:
        """Normalize a '|'-delimited filter field; '' or 'None' -> []."""
        value = value.strip()
        if value in ("", "None"):
            return []
        return [part for part in value.split("|") if part]


    def parse_record(record: dict) -> QueryLogEntry | None:
        """Parse one CloudWatch record into a QueryLogEntry, or None if it is not a
        NameRes lookup line we recognize."""
        message = record.get("@message")
        line = message["log"] if isinstance(message, dict) else message
        if not line or "Lookup query to Solr" not in line:
            return None

        m = LOOKUP_LINE_RE.search(line)
        if not m:
            raise ValueError(f"Unparseable NameRes lookup line: {line!r}")
        g = m.groupdict()

        k8s = message.get("kubernetes", {}) if isinstance(message, dict) else {}
        image = (k8s.get("container_image", "") or "")

        return QueryLogEntry(
            time=datetime.fromisoformat(record["@timestamp"]),
            query=g["query"],
            query_length=len(g["query"]),
            autocomplete=g["autocomplete"] == "True",
            highlighting=g["highlighting"] == "True",
            offset=int(g["offset"]),
            limit=int(g["limit"]),
            biolink_types=ast.literal_eval(g["biolink_types"]),
            only_prefixes=_parse_filter_list(g["only_prefixes"]),
            exclude_prefixes=_parse_filter_list(g["exclude_prefixes"]),
            only_taxa=_parse_filter_list(g["only_taxa"]),
            took_ms=float(g["took"]),
            solr_wait_ms=float(g["solr"]),
            slow_query="SLOW QUERY" in line,
            pod_name=k8s.get("pod_name", ""),
            image_tag=image.split(":")[-1] if image else "",
        )

    return QueryLogEntry, parse_record


@app.cell
def loader(LOG_PATH, QueryLogEntry, json, mo, parse_record):
    raw_records = json.loads(LOG_PATH.read_text())

    entries: list[QueryLogEntry] = []
    skipped_records = 0
    for _rec in raw_records:
        _entry = parse_record(_rec)
        if _entry is None:
            skipped_records += 1
        else:
            entries.append(_entry)

    mo.md(
        f"Parsed **{len(entries):,}** lookup entries from "
        f"**{len(raw_records):,}** records "
        f"(skipped {skipped_records} non-lookup records)."
    )
    return (entries,)


@app.cell
def dataframe(asdict, entries: "list[QueryLogEntry]", np, pd):
    df = pd.DataFrame([asdict(e) for e in entries])
    df["time"] = pd.to_datetime(df["time"])

    # Derived columns to make slicing the data easier.
    df["num_biolink_types"] = df["biolink_types"].apply(len)
    df["has_biolink_filter"] = df["num_biolink_types"] > 0
    df["has_only_prefixes"] = df["only_prefixes"].apply(len) > 0
    df["has_exclude_prefixes"] = df["exclude_prefixes"].apply(len) > 0
    df["has_taxa_filter"] = df["only_taxa"].apply(len) > 0
    # Total request time minus the Solr wait = time spent in the NameRes app itself.
    df["app_overhead_ms"] = df["took_ms"] - df["solr_wait_ms"]
    df["mode"] = np.where(df["autocomplete"], "autocomplete", "exact")

    df = df.sort_values("time").reset_index(drop=True)
    df
    return


if __name__ == "__main__":
    app.run()
