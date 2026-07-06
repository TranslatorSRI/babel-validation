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

    return Path, alt, asdict, ast, dataclass, datetime, json, mo, np, pd, re


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
    return (df,)


@app.cell(hide_code=True)
def measures_header(mo):
    mo.md(r"""
    # Overall measures

    Headline numbers for the whole log, then a latency breakdown by query mode.
    NameRes reports two latencies per request: **`took_ms`** (total request time)
    and **`solr_wait_ms`** (time waiting for Solr). Their difference is the
    **app overhead** spent inside the NameRes web layer.
    """)
    return


@app.cell
def overall_stats(df, mo):
    _n = len(df)
    _span = df["time"].max() - df["time"].min()
    _reqs_per_day = _n / (_span.total_seconds() / 86400) if _span.total_seconds() else float("nan")

    mo.md(f"""
    - **Time range:** {df['time'].min()} → {df['time'].max()} &nbsp; ({_span})
    - **Total lookups:** {_n:,} &nbsp; (~{_reqs_per_day:,.0f} / day)
    - **Unique query strings:** {df['query'].nunique():,}
    - **Mode split:** {int(df['autocomplete'].sum()):,} autocomplete / {int((~df['autocomplete']).sum()):,} exact
    - **Slow queries (WARNING):** {int(df['slow_query'].sum()):,} ({df['slow_query'].mean() * 100:.2f}%)
    - **Total latency:** median {df['took_ms'].median():.2f} ms, mean {df['took_ms'].mean():.2f} ms, max {df['took_ms'].max():,.2f} ms
    - **Solr wait:** median {df['solr_wait_ms'].median():.2f} ms, mean {df['solr_wait_ms'].mean():.2f} ms, max {df['solr_wait_ms'].max():,.2f} ms
    - **App overhead:** median {df['app_overhead_ms'].median():.2f} ms, mean {df['app_overhead_ms'].mean():.2f} ms
    - **Query length (chars):** median {int(df['query_length'].median())}, mean {df['query_length'].mean():.1f}, max {df['query_length'].max()}
    - **Filters used:** biolink_types {df['has_biolink_filter'].mean() * 100:.0f}%, only_prefixes {df['has_only_prefixes'].mean() * 100:.0f}%, exclude_prefixes {df['has_exclude_prefixes'].mean() * 100:.0f}%, only_taxa {df['has_taxa_filter'].mean() * 100:.0f}%
    """)
    return


@app.cell
def latency_table(df, pd):
    def latency_summary_rows(frame: pd.DataFrame, scope: str) -> list[dict]:
        """Percentile summary for each latency metric over `frame`."""
        rows = []
        for metric in ["took_ms", "solr_wait_ms", "app_overhead_ms"]:
            s = frame[metric]
            rows.append(
                {
                    "scope": scope,
                    "metric": metric,
                    "count": len(frame),
                    "mean": round(s.mean(), 2),
                    "p50": round(s.median(), 2),
                    "p90": round(s.quantile(0.90), 2),
                    "p95": round(s.quantile(0.95), 2),
                    "p99": round(s.quantile(0.99), 2),
                    "max": round(s.max(), 2),
                }
            )
        return rows


    _rows = latency_summary_rows(df, "overall")
    for _mode, _grp in df.groupby("mode"):
        _rows += latency_summary_rows(_grp, _mode)

    latency_table = pd.DataFrame(_rows)
    latency_table
    return


@app.cell(hide_code=True)
def viz_header(mo):
    mo.md(r"""
    # Visualizations

    Interactive charts characterizing NameRes query performance. Because latency is
    extremely heavy-tailed (a handful of requests take seconds while most take
    ~13 ms), several charts default to a log scale. Use the controls to switch
    metric and scale.
    """)
    return


@app.cell
def viz_setup(alt, mo):
    # Altair caps embedded data at 5,000 rows by default; we have ~10k, so lift it.
    alt.data_transformers.disable_max_rows()
    mo.md("_Altair row limit disabled for this session._")
    return


@app.cell
def viz_controls(mo):
    metric_choice = mo.ui.dropdown(
        options={
            "Total request (took_ms)": "took_ms",
            "Solr wait (solr_wait_ms)": "solr_wait_ms",
            "App overhead (app_overhead_ms)": "app_overhead_ms",
        },
        value="Total request (took_ms)",
        label="Latency metric",
    )
    use_log = mo.ui.checkbox(value=True, label="Log scale")
    max_ms = mo.ui.slider(
        start=50, stop=2000, step=50, value=500,
        label="Max ms (linear scale only)", show_value=True,
    )
    mo.hstack([metric_choice, use_log, max_ms], justify="start", gap=2)
    return max_ms, metric_choice, use_log


@app.cell
def latency_hist(alt, df, max_ms, metric_choice, mo, np, use_log):
    _metric = metric_choice.value

    if use_log.value:
        _d = df[df[_metric] > 0].assign(_logv=np.log10(df.loc[df[_metric] > 0, _metric]))
        _x = alt.X("_logv:Q", bin=alt.Bin(maxbins=60), title=f"log10({_metric})")
    else:
        _d = df[df[_metric] <= max_ms.value]
        _x = alt.X(f"{_metric}:Q", bin=alt.Bin(maxbins=60), title=f"{_metric} (ms)")

    _hist = (
        alt.Chart(_d)
        .mark_bar(opacity=0.75)
        .encode(
            _x,
            alt.Y("count()", title="requests", stack=None),
            alt.Color("mode:N", title="Query mode"),
            tooltip=[alt.Tooltip("count()", title="requests"), "mode:N"],
        )
        .properties(height=280, title=f"Distribution of {_metric}")
    )
    mo.ui.altair_chart(_hist)
    return


@app.cell
def box_by_mode(alt, df):
    # Total latency by mode (log scale, since the tail spans ~5 orders of magnitude).
    _bm = (
        alt.Chart(df[df["took_ms"] > 0])
        .mark_boxplot(extent=1.5)
        .encode(
            alt.X("mode:N", title="Query mode"),
            alt.Y("took_ms:Q", scale=alt.Scale(type="log"), title="Total latency (ms, log)"),
            alt.Color("mode:N", legend=None),
        )
        .properties(height=320, title="Total latency by query mode")
    )
    _bm
    return


@app.cell
def solr_by_limit(alt, df):
    # Solr wait by requested result limit, split by mode.
    _bl = (
        alt.Chart(df[df["solr_wait_ms"] > 0])
        .mark_boxplot(extent=1.5)
        .encode(
            alt.X("limit:O", title="limit (requested results)"),
            alt.Y("solr_wait_ms:Q", scale=alt.Scale(type="log"), title="Solr wait (ms, log)"),
            alt.Color("mode:N", title="Query mode"),
            alt.XOffset("mode:N"),
        )
        .properties(height=320, title="Solr wait time by result limit and mode")
    )
    _bl
    return


@app.cell
def latency_vs_qlen(alt, df, mo):
    # Median and p95 Solr wait vs query length (chars), aggregated per length & mode.
    _q = df[df["query_length"] <= 40]
    _agg = (
        _q.groupby(["query_length", "mode"])
        .agg(
            median_ms=("solr_wait_ms", "median"),
            p95_ms=("solr_wait_ms", lambda s: s.quantile(0.95)),
            n=("solr_wait_ms", "size"),
        )
        .reset_index()
    )
    _median_line = (
        alt.Chart(_agg)
        .mark_line(point=True)
        .encode(
            alt.X("query_length:Q", title="Query length (chars)"),
            alt.Y("median_ms:Q", title="Solr wait (ms)"),
            alt.Color("mode:N", title="Query mode"),
            tooltip=["query_length", "mode", "median_ms", "p95_ms", "n"],
        )
        .properties(height=300, title="Median Solr wait vs query length (queries ≤ 40 chars)")
    )
    mo.ui.altair_chart(_median_line)
    return


@app.cell
def qlen_dist(alt, df):
    # Distribution of query lengths (capped at 40 chars for readability).
    _qd = (
        alt.Chart(df[df["query_length"] <= 40])
        .mark_bar()
        .encode(
            alt.X("query_length:Q", bin=alt.Bin(maxbins=40), title="Query length (chars)"),
            alt.Y("count()", title="requests"),
            alt.Color("mode:N", title="Query mode"),
        )
        .properties(height=280, title="Query length distribution")
    )
    _qd
    return


@app.cell(hide_code=True)
def time_caption(mo):
    mo.md(r"""
    ### Temporal coverage

    **Caveat:** this export is a capped/non-uniform sample of log lines (CloudWatch
    returns at most 10,000 rows), so the counts below reflect *what is in the export*,
    not true NameRes traffic volume. It is shown only to confirm the time span the
    sample covers.
    """)
    return


@app.cell
def time_chart(alt, df):
    _daily = df.set_index("time").resample("D").size().reset_index(name="lines")
    _tc = (
        alt.Chart(_daily)
        .mark_bar()
        .encode(
            alt.X("time:T", title="Day"),
            alt.Y("lines:Q", title="log lines in export"),
            tooltip=["time:T", "lines:Q"],
        )
        .properties(height=240, title="Sampled log lines per day")
    )
    _tc
    return


@app.cell(hide_code=True)
def slow_header(mo):
    mo.md(r"""
    # Slow queries

    NameRes logs a `WARNING: SLOW QUERY` when a lookup crosses its slow-query
    threshold. These are the requests an ElasticSearch backend would most need to
    improve on. Below: how the slow-query rate varies by mode and result limit, and
    the actual slowest queries in the sample.
    """)
    return


@app.cell
def slow_rate(alt, df):
    _slow = (
        df.groupby(["limit", "mode"])["slow_query"].mean().reset_index()
    )
    _sr = (
        alt.Chart(_slow)
        .mark_bar()
        .encode(
            alt.X("limit:O", title="limit (requested results)"),
            alt.Y("slow_query:Q", title="fraction slow", axis=alt.Axis(format="%")),
            alt.Color("mode:N", title="Query mode"),
            alt.XOffset("mode:N"),
            tooltip=["limit", "mode", alt.Tooltip("slow_query:Q", format=".1%")],
        )
        .properties(height=300, title="Slow-query rate by result limit and mode")
    )
    _sr
    return


@app.cell
def slowest_queries(df):
    # The actual slowest lookups in the sample (by Solr wait time).
    slowest_queries = (
        df.nlargest(25, "solr_wait_ms")[
            ["time", "query", "mode", "limit", "num_biolink_types",
             "has_exclude_prefixes", "solr_wait_ms", "took_ms"]
        ]
        .reset_index(drop=True)
    )
    slowest_queries
    return


@app.cell(hide_code=True)
def bench_header(mo):
    mo.md(r"""
    # Benchmark export

    To compare Solr against an ElasticSearch implementation, we distill the log into
    a **replayable benchmark**: one case per unique `(query, params)` combination,
    each carrying the parameters needed to reissue the lookup plus the **observed
    Solr baseline latency**. Replaying these cases against both backends and
    comparing to `baseline_solr` gives an apples-to-apples latency comparison on
    real production queries.
    """)
    return


@app.cell
def bench_build(df, mo, pd):
    def build_benchmark_cases(frame: pd.DataFrame) -> list[dict]:
        """Deduplicate to one case per unique (query, params) and attach the observed
        Solr baseline latency for each case."""
        _join = lambda xs: "|".join(xs)
        src = frame.assign(
            _bt=frame["biolink_types"].apply(_join),
            _op=frame["only_prefixes"].apply(_join),
            _ep=frame["exclude_prefixes"].apply(_join),
            _ot=frame["only_taxa"].apply(_join),
        )
        key = ["query", "autocomplete", "highlighting", "offset", "limit",
               "_bt", "_op", "_ep", "_ot"]

        cases = []
        for _, g in src.groupby(key, sort=False):
            r0 = g.iloc[0]
            cases.append(
                {
                    "query": r0["query"],
                    "autocomplete": bool(r0["autocomplete"]),
                    "highlighting": bool(r0["highlighting"]),
                    "offset": int(r0["offset"]),
                    "limit": int(r0["limit"]),
                    "biolink_types": list(r0["biolink_types"]),
                    "only_prefixes": list(r0["only_prefixes"]),
                    "exclude_prefixes": list(r0["exclude_prefixes"]),
                    "only_taxa": list(r0["only_taxa"]),
                    "baseline_solr": {
                        "n_observed": int(len(g)),
                        "solr_wait_ms_p50": round(float(g["solr_wait_ms"].median()), 3),
                        "solr_wait_ms_p95": round(float(g["solr_wait_ms"].quantile(0.95)), 3),
                        "took_ms_p50": round(float(g["took_ms"].median()), 3),
                        "ever_slow": bool(g["slow_query"].any()),
                        "first_seen": g["time"].min().isoformat(),
                        "last_seen": g["time"].max().isoformat(),
                    },
                }
            )
        return cases


    benchmark_cases = build_benchmark_cases(df)
    benchmark_df = pd.json_normalize(benchmark_cases)
    mo.vstack([
        mo.md(f"**{len(benchmark_cases):,}** unique benchmark cases "
              f"(from {len(df):,} log rows)."),
        benchmark_df,
    ])
    return (benchmark_cases,)


@app.cell
def bench_export(LOG_PATH, Path, benchmark_cases, df, json, mo):
    BENCHMARK_DIR = Path("benchmark")
    BENCHMARK_DIR.mkdir(exist_ok=True)
    benchmark_path = BENCHMARK_DIR / "nameres_solr_benchmark_2026-07-06.json"

    benchmark_payload = {
        "source_log": LOG_PATH.name,
        "generated_from_rows": int(len(df)),
        "num_cases": len(benchmark_cases),
        "cases": benchmark_cases,
    }
    _benchmark_json = json.dumps(benchmark_payload, indent=2)
    benchmark_path.write_text(_benchmark_json)

    mo.vstack([
        mo.md(
            f"Wrote **{len(benchmark_cases):,}** benchmark cases to "
            f"`{benchmark_path}` ({len(_benchmark_json) / 1e6:.2f} MB)."
        ),
        mo.download(
            data=_benchmark_json.encode("utf-8"),
            filename=benchmark_path.name,
            mimetype="application/json",
            label="Download benchmark JSON",
        ),
    ])
    return


if __name__ == "__main__":
    app.run()
