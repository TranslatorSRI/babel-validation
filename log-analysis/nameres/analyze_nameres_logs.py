import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def title(mo):
    mo.md(r"""
    # NameRes Autocomplete Log Analysis

    Analysis of **autocomplete** (`autocomplete=True`) queries against **NameRes**
    (Name Resolver), the Solr-backed production name lookup service. The goal is to
    characterize how NameRes performs on incremental type-ahead queries, and to
    build a **benchmark** we can replay against an alternate NameRes implementation
    backed by **ElasticSearch**.

    Autocomplete is the case worth isolating. It is a small slice of NameRes traffic
    (~3% of lookups in a general export) but it is by far the worst-behaved: in a
    mixed sample, autocomplete p95 Solr wait was ~2.8 s against ~43 ms for exact
    lookups, with a p99 of several minutes. It is also the most latency-sensitive
    mode, since a user is waiting on it between keystrokes.

    Each log line reports two latencies: total request time (`took`) and the portion
    spent **waiting for Solr**. A typical line looks like:

    ```
    INFO:api.server:Lookup query to Solr for "neutrop" (autocomplete=True,
      highlighting=False, offset=0, limit=20, biolink_types=[''], only_prefixes=,
      exclude_prefixes=, only_taxa=None) took 22.01ms (with 21.30ms waiting for Solr)
    ```

    Exports are downloaded from CloudWatch Logs Insights with the autocomplete
    filter applied at query time, so the whole result budget is spent on the mode we
    care about rather than on the ~97% of traffic we do not:

    ```
    SOURCE "[application logs]" START=-10w END=now
    | fields @timestamp, @message, @logStream, @log
    | filter @message like /Lookup query to Solr.*autocomplete=True/
    | sort @timestamp desc
    | limit 10000
    ```

    Non-autocomplete analysis lived here previously and will return in its own
    notebook; mixing the two made every aggregate a weighted average of two
    populations that behave nothing alike.
    """)
    return


@app.cell
def imports():
    import json
    import re
    import ast
    from dataclasses import dataclass, field, asdict
    from datetime import datetime
    from itertools import combinations
    from pathlib import Path

    import marimo as mo
    import pandas as pd
    import numpy as np
    import altair as alt

    return (
        alt,
        asdict,
        ast,
        combinations,
        dataclass,
        datetime,
        json,
        mo,
        np,
        pd,
        re,
    )


@app.cell
def log_path(mo):
    # Anchor every path on the notebook's own location, not the process cwd. marimo
    # inherits the cwd of whatever launched it (repo root, if started from there),
    # so cwd-relative paths silently write generated artifacts into the wrong
    # directory — past the `log-analysis/nameres/.gitignore` that exists to catch
    # them — depending on where the notebook was opened from.
    NOTEBOOK_DIR = mo.notebook_dir()
    REPO_ROOT = NOTEBOOK_DIR.parents[1]

    # Raw NameRes autocomplete-only log exports (CloudWatch Logs Insights JSON
    # dumps). Every `nameres-autocomplete-only-*.json` file in LOG_DIR is loaded and
    # concatenated, so widening the window means dropping in another export.
    #
    # The glob is deliberately narrow: LOG_DIR also holds general (all-mode) exports,
    # and loading those here would both dilute the analysis and trip the
    # overlapping-span check below.
    #
    # These exports are large and are intentionally NOT checked into the repository:
    # `data/` is a symlink to a shared, gitignored data directory.
    LOG_DIR = REPO_ROOT / "data" / "log-analysis"
    LOG_PATHS = sorted(LOG_DIR.glob("nameres-autocomplete-only-*.json"))

    if not LOG_PATHS:
        raise FileNotFoundError(
            f"No autocomplete-only log exports matched "
            f"{LOG_DIR}/nameres-autocomplete-only-*.json — is the data/ symlink in place?"
        )

    mo.md(
        f"Reading **{len(LOG_PATHS)}** autocomplete-only export(s) from `{LOG_DIR}`:\n\n"
        + "\n".join(f"- `{_p.name}` ({_p.stat().st_size / 1e6:.1f} MB)" for _p in LOG_PATHS)
    )
    return LOG_PATHS, NOTEBOOK_DIR


@app.cell(hide_code=True)
def load_section(mo):
    mo.md(r"""
    ## Loading the log files into a dataclass

    Each record in a JSON export wraps a single Solr `lookup` log line. We parse
    each line into a `QueryLogEntry` dataclass capturing the query, its parameters,
    and both latency measurements. Filter fields (`only_prefixes`, `exclude_prefixes`,
    `only_taxa`) are `|`-delimited in the log and normalized here into lists; an empty
    value or the literal `None` becomes an empty list (i.e. no filter).

    All autocomplete-only exports in `LOG_DIR` are loaded together. Because Logs
    Insights exports are plain time-window dumps with no record IDs, two exports
    covering the same window would silently double-count the same lookups — so we
    compute each file's time span up front and **refuse to load overlapping exports**
    rather than skew every statistic downstream. (De-duplicating overlapping exports
    is future work; for now the fix is to re-export non-overlapping windows.)
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
        source_file: str = ""   # export the line came from, for provenance


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


    def parse_record(record: dict, source_file: str = "") -> QueryLogEntry | None:
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
            source_file=source_file,
        )

    return QueryLogEntry, parse_record


@app.cell
def span_helpers(combinations, datetime):
    def log_file_span(records: list[dict]) -> tuple[datetime, datetime]:
        """Earliest and latest `@timestamp` across every record in one export.

        Uses the raw records rather than the parsed lookups, so a file's span
        reflects the window that was exported even if few lines are lookups.
        """
        times = [datetime.fromisoformat(rec["@timestamp"]) for rec in records]
        if not times:
            raise ValueError("Log export contains no records")
        return min(times), max(times)


    def assert_no_overlapping_spans(spans: dict[str, tuple[datetime, datetime]]) -> None:
        """Raise if any two exports cover overlapping time ranges.

        Logs Insights exports carry no per-record ID, so overlapping windows would
        double-count the same lookups and quietly bias every statistic below. Until
        we have a way to de-duplicate across files, refuse to load them together.

        Spans are treated as closed intervals: two exports that merely touch at an
        endpoint are rejected, because that shared instant really can hold the same
        log line twice.
        """
        clashes = [
            (name_a, span_a, name_b, span_b)
            for (name_a, span_a), (name_b, span_b) in combinations(sorted(spans.items()), 2)
            if span_a[0] <= span_b[1] and span_b[0] <= span_a[1]
        ]
        if clashes:
            detail = "\n".join(
                f"  - {a} ({a_span[0]} .. {a_span[1]})\n"
                f"    overlaps {b} ({b_span[0]} .. {b_span[1]})"
                for a, a_span, b, b_span in clashes
            )
            raise ValueError(
                f"{len(clashes)} pair(s) of log exports cover overlapping time "
                f"spans, which would double-count lookups:\n{detail}\n"
                f"Remove or re-export one of each pair so the windows are disjoint."
            )

    return assert_no_overlapping_spans, log_file_span


@app.cell
def loader(
    LOG_PATHS,
    QueryLogEntry,
    assert_no_overlapping_spans,
    json,
    log_file_span,
    mo,
    parse_record,
    pd,
):
    # Pass 1: read every export and work out what window it covers, so that an
    # overlap fails fast rather than after minutes of regex parsing.
    records_by_file = {path.name: json.loads(path.read_text()) for path in LOG_PATHS}
    log_file_spans = {name: log_file_span(recs) for name, recs in records_by_file.items()}
    assert_no_overlapping_spans(log_file_spans)

    # Pass 2: parse the lookup lines, oldest export first.
    raw_records: list[dict] = []
    entries: list[QueryLogEntry] = []
    skipped_records = 0
    _summary_rows = []
    for _name in sorted(records_by_file, key=lambda n: log_file_spans[n][0]):
        _recs = records_by_file[_name]
        _kept = 0
        for _rec in _recs:
            _entry = parse_record(_rec, source_file=_name)
            if _entry is None:
                skipped_records += 1
            else:
                entries.append(_entry)
                _kept += 1
        raw_records.extend(_recs)
        _start, _end = log_file_spans[_name]
        _summary_rows.append(
            {
                "file": _name,
                "records": len(_recs),
                "lookups": _kept,
                "from": _start,
                "to": _end,
                "span": _end - _start,
            }
        )

    log_file_summary = pd.DataFrame(_summary_rows)

    mo.vstack(
        [
            mo.md(
                f"Parsed **{len(entries):,}** lookup entries from "
                f"**{len(raw_records):,}** records across "
                f"**{len(LOG_PATHS)}** export(s) "
                f"(skipped {skipped_records:,} non-lookup records)."
            ),
            log_file_summary,
        ]
    )
    return entries, log_file_summary


@app.cell
def dataframe(asdict, entries: "list[QueryLogEntry]", np, pd):
    # `pod_name` and `image_tag` are parsed onto every QueryLogEntry but deliberately
    # kept out of `df`. Nothing in this notebook analyses them, and `df` is the one
    # frame rendered in full — so it is the only place they reach the shared HTML
    # export (every other displayed table names its columns explicitly). They remain
    # on `entries` for a future notebook comparing NameRes versions or Solr
    # instances; rebuild from `entries` there rather than adding them back here.
    df = pd.DataFrame([asdict(e) for e in entries]).drop(columns=["pod_name", "image_tag"])
    df["time"] = pd.to_datetime(df["time"])

    # This notebook is autocomplete-only; a stray exact lookup means the export was
    # built with the wrong Logs Insights filter, which would quietly bias every
    # aggregate below.
    if not df["autocomplete"].all():
        raise ValueError(
            f"{int((~df['autocomplete']).sum()):,} of {len(df):,} entries are not "
            f"autocomplete=True — was this export downloaded without the "
            f"`autocomplete=True` filter?"
        )

    # Some clients send biolink_types=[''] (an empty string rather than no filter);
    # treat that as "no filter" so the filter-usage counts mean what they say.
    df["biolink_types"] = df["biolink_types"].apply(lambda ts: [t for t in ts if t])

    # Derived columns to make slicing the data easier.
    df["num_biolink_types"] = df["biolink_types"].apply(len)
    df["has_biolink_filter"] = df["num_biolink_types"] > 0
    df["has_only_prefixes"] = df["only_prefixes"].apply(len) > 0
    df["has_exclude_prefixes"] = df["exclude_prefixes"].apply(len) > 0
    df["has_taxa_filter"] = df["only_taxa"].apply(len) > 0
    # Total request time minus the Solr wait = time spent in the NameRes app itself.
    df["app_overhead_ms"] = df["took_ms"] - df["solr_wait_ms"]
    # Short prefixes are the interesting case for autocomplete, so bucket finely at
    # the low end and coarsely at the top.
    df["query_length_bucket"] = pd.cut(
        df["query_length"],
        bins=[0, 3, 5, 8, 12, 20, np.inf],
        labels=["1-3", "4-5", "6-8", "9-12", "13-20", "21+"],
    )

    df = df.sort_values("time").reset_index(drop=True)
    df
    return (df,)


@app.cell(hide_code=True)
def measures_header(mo):
    mo.md(r"""
    # Overall measures

    Headline numbers for the autocomplete traffic in the export, then a latency
    breakdown by requested result `limit`. NameRes reports two latencies per
    request: **`took_ms`** (total request time) and **`solr_wait_ms`** (time waiting
    for Solr). Their difference is the **app overhead** spent inside the NameRes web
    layer — and for autocomplete it is negligible next to the Solr wait, which is
    the whole point: the fix has to come from the search backend.
    """)
    return


@app.cell
def overall_stats(df, mo):
    _n = len(df)
    _span = df["time"].max() - df["time"].min()
    _reqs_per_day = _n / (_span.total_seconds() / 86400) if _span.total_seconds() else float("nan")

    mo.md(f"""
    - **Time range:** {df['time'].min()} → {df['time'].max()} &nbsp; ({_span})
    - **Autocomplete lookups:** {_n:,} &nbsp; (~{_reqs_per_day:,.0f} / day)
    - **Unique query strings:** {df['query'].nunique():,}
    - **Slow queries (WARNING):** {int(df['slow_query'].sum()):,} ({df['slow_query'].mean() * 100:.2f}%)
    - **Total latency:** median {df['took_ms'].median():.2f} ms, p95 {df['took_ms'].quantile(0.95):,.2f} ms, max {df['took_ms'].max():,.2f} ms
    - **Solr wait:** median {df['solr_wait_ms'].median():.2f} ms, p95 {df['solr_wait_ms'].quantile(0.95):,.2f} ms, max {df['solr_wait_ms'].max():,.2f} ms
    - **App overhead:** median {df['app_overhead_ms'].median():.2f} ms, p95 {df['app_overhead_ms'].quantile(0.95):.2f} ms &nbsp; ({df['app_overhead_ms'].sum() / df['took_ms'].sum() * 100:.1f}% of total time)
    - **Query length (chars):** median {int(df['query_length'].median())}, mean {df['query_length'].mean():.1f}, max {df['query_length'].max()}
    - **Result limits requested:** {', '.join(f'{_k}×{_v:,}' for _k, _v in df['limit'].value_counts().items())}
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


    # Everything here is autocomplete, so the interesting splits are the requested
    # result limit and how far into the word the user has typed.
    _rows = latency_summary_rows(df, "overall")
    for _limit, _grp in df.groupby("limit"):
        _rows += latency_summary_rows(_grp, f"limit={_limit}")
    for _bucket, _grp in df.groupby("query_length_bucket", observed=True):
        _rows += latency_summary_rows(_grp, f"qlen {_bucket}")

    latency_table = pd.DataFrame(_rows)
    latency_table
    return


@app.cell(hide_code=True)
def viz_header(mo):
    mo.md(r"""
    # Visualizations

    Interactive charts characterizing autocomplete performance. Because latency is
    extremely heavy-tailed (a handful of requests take minutes while most take
    tens of milliseconds), several charts default to a log scale. Use the controls
    to switch metric and scale.
    """)
    return


@app.cell
def viz_setup(alt, mo):
    # Altair caps embedded data at 5,000 rows by default. The autocomplete-only
    # exports are well under that today, but lifting the cap keeps the charts
    # working as more export windows are added.
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
        alt.Chart(_d[["_logv", _metric, "limit"]] if use_log.value else _d[[_metric, "limit"]])
        .mark_bar(opacity=0.75)
        .encode(
            _x,
            alt.Y("count()", title="requests", stack=None),
            alt.Color("limit:N", title="Result limit"),
            tooltip=[alt.Tooltip("count()", title="requests"), "limit:N"],
        )
        .properties(height=280, title=f"Distribution of {_metric} (autocomplete only)")
    )
    mo.ui.altair_chart(_hist)
    return


@app.cell
def box_by_qlen(alt, df):
    # Solr wait by how many characters the user has typed. Short prefixes match a
    # huge slice of the index, so this is where autocomplete is expected to hurt.
    _bq = (
        alt.Chart(df.loc[df["solr_wait_ms"] > 0, ["query_length_bucket", "solr_wait_ms"]])
        .mark_boxplot(extent=1.5)
        .encode(
            alt.X("query_length_bucket:N", title="Query length (chars)", sort=None),
            alt.Y("solr_wait_ms:Q", scale=alt.Scale(type="log"), title="Solr wait (ms, log)"),
            alt.Color("query_length_bucket:N", legend=None),
        )
        .properties(height=320, title="Solr wait by query length")
    )
    _bq
    return


@app.cell
def solr_by_limit(alt, df):
    # Solr wait by requested result limit. Autocomplete clients that ask for 100
    # results pay for all 100, on every keystroke.
    _bl = (
        alt.Chart(df.loc[df["solr_wait_ms"] > 0, ["limit", "solr_wait_ms"]])
        .mark_boxplot(extent=1.5)
        .encode(
            alt.X("limit:O", title="limit (requested results)"),
            alt.Y("solr_wait_ms:Q", scale=alt.Scale(type="log"), title="Solr wait (ms, log)"),
            alt.Color("limit:O", legend=None),
        )
        .properties(height=320, title="Solr wait time by result limit")
    )
    _bl
    return


@app.cell
def latency_vs_qlen(alt, df, mo):
    # Median and p95 Solr wait vs exact query length (chars), aggregated per length.
    _q = df[df["query_length"] <= 40]
    _agg = (
        _q.groupby("query_length")
        .agg(
            median_ms=("solr_wait_ms", "median"),
            p95_ms=("solr_wait_ms", lambda s: s.quantile(0.95)),
            n=("solr_wait_ms", "size"),
        )
        .reset_index()
        .melt(
            id_vars=["query_length", "n"],
            value_vars=["median_ms", "p95_ms"],
            var_name="statistic",
            value_name="solr_wait_ms",
        )
    )
    _qlen_line = (
        alt.Chart(_agg)
        .mark_line(point=True)
        .encode(
            alt.X("query_length:Q", title="Query length (chars)"),
            alt.Y("solr_wait_ms:Q", scale=alt.Scale(type="log"), title="Solr wait (ms, log)"),
            alt.Color("statistic:N", title="Statistic"),
            tooltip=["query_length", "statistic", "solr_wait_ms", "n"],
        )
        .properties(height=300, title="Solr wait vs query length (queries ≤ 40 chars)")
    )
    mo.ui.altair_chart(_qlen_line)
    return


@app.cell
def qlen_dist(alt, df):
    # Distribution of query lengths (capped at 40 chars for readability).
    _qd = (
        alt.Chart(df.loc[df["query_length"] <= 40, ["query_length"]])
        .mark_bar()
        .encode(
            alt.X("query_length:Q", bin=alt.Bin(maxbins=40), title="Query length (chars)"),
            alt.Y("count()", title="requests"),
        )
        .properties(height=280, title="Autocomplete query length distribution")
    )
    _qd
    return


@app.cell(hide_code=True)
def time_caption(mo):
    mo.md(r"""
    ### Temporal coverage

    Unlike the general (all-mode) exports, the autocomplete-only query is selective
    enough that a 10-week window comes back well under the CloudWatch 10,000-row
    cap — so this is the *complete* autocomplete population for the window, not a
    sample of it. The per-day counts below are therefore real traffic volume, though
    they are still subject to the log retention window.
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
    improve on, and in autocomplete they land directly in a user's typing loop.
    Below: how the slow-query rate varies by result limit and query length, and the
    actual slowest queries in the export.
    """)
    return


@app.cell
def slow_rate(alt, df):
    _slow = (
        df.groupby(["limit", "query_length_bucket"], observed=True)["slow_query"]
        .agg(["mean", "size"])
        .reset_index()
        .rename(columns={"mean": "fraction_slow", "size": "n"})
    )
    _sr = (
        alt.Chart(_slow)
        .mark_bar()
        .encode(
            alt.X("limit:O", title="limit (requested results)"),
            alt.Y("fraction_slow:Q", title="fraction slow", axis=alt.Axis(format="%")),
            alt.Color("query_length_bucket:N", title="Query length", sort=None),
            alt.XOffset("query_length_bucket:N", sort=None),
            tooltip=["limit", "query_length_bucket", alt.Tooltip("fraction_slow:Q", format=".1%"), "n"],
        )
        .properties(height=300, title="Slow-query rate by result limit and query length")
    )
    _sr
    return


@app.cell
def slowest_queries(df):
    # The actual slowest autocomplete lookups in the export (by Solr wait time).
    slowest_queries = (
        df.nlargest(25, "solr_wait_ms")[
            ["time", "query", "query_length", "limit", "num_biolink_types",
             "has_exclude_prefixes", "solr_wait_ms", "took_ms"]
        ]
        .reset_index(drop=True)
    )
    slowest_queries
    return


@app.cell
def chain_header(mo):
    mo.md(r"""
    # Typing chains: what were they actually looking for?

    An autocomplete log line is one keystroke's worth of a query, so `"diab"` on its
    own says little. Reconstructing the **typing chain** — `diab` → `diabe` →
    `diabet` → `diabetes type 2` — tells us what the user was reaching for, which
    prefixes were expensive on the way there, and how many round trips a single
    lookup actually costs.

    The logs carry **no session or user ID**, so chains are inferred. Consecutive
    lookups are joined into one chain when all of the following hold:

    1. they share the same request shape (`limit`, `biolink_types`, `only_prefixes`,
       `exclude_prefixes`, `only_taxa`) — i.e. the same client widget;
    2. one query is a **prefix of the other**, case-insensitively (so both typing
       forward and backspacing extend a chain);
    3. they are less than `chain_gap` apart in time.

    This is a heuristic, and it has two known failure modes: two users typing the
    same term at the same moment through the same widget merge into one chain, and a
    user who pauses longer than `chain_gap` is split into two. In this export the
    median gap between prefix-compatible consecutive queries is ~2 s and the 90th
    percentile is ~43 s, so the result is not very sensitive to the threshold —
    between a 30 s and a 60 s gap the chain count moves by under 3%.

    Two "final term" columns are produced, because they answer different questions:

    - **`final_query`** — the chronologically last query in the chain, i.e. what the
      user was left looking at.
    - **`longest_query`** — the longest query in the chain, i.e. the fullest term
      they ever typed. When a user backspaces at the end (`salisylic` → … → `salic`),
      this is the one you want.
    """)
    return


@app.cell
def chain_controls(mo):
    chain_gap = mo.ui.slider(
        start=5, stop=300, step=5, value=60,
        label="Max seconds between keystrokes in one chain", show_value=True,
    )
    chain_gap
    return (chain_gap,)


@app.cell
def chain_helpers(pd):
    def request_shape(row: pd.Series) -> tuple:
        """The parameters that identify one client widget's request shape.

        Two lookups with different shapes came from different callers (or a caller
        that changed its filters), so they never belong to the same typing chain.
        """
        return (
            row["limit"],
            tuple(row["biolink_types"]),
            tuple(row["only_prefixes"]),
            tuple(row["exclude_prefixes"]),
            tuple(row["only_taxa"]),
        )


    def assign_chains(frame: pd.DataFrame, gap: pd.Timedelta) -> pd.Series:
        """Group consecutive autocomplete lookups into inferred typing chains.

        `frame` must be sorted by time. Returns a chain ID per row, aligned to
        `frame.index`. See the section header for the joining rules and caveats.
        """
        last_by_shape: dict[tuple, tuple[int, str, pd.Timestamp]] = {}
        chain_ids: list[int] = []
        next_id = 0
        for _, row in frame.iterrows():
            shape = request_shape(row)
            query = row["query"].casefold()
            previous = last_by_shape.get(shape)
            if (
                previous is not None
                and row["time"] - previous[2] <= gap
                and (query.startswith(previous[1]) or previous[1].startswith(query))
            ):
                chain_id = previous[0]
            else:
                chain_id = next_id
                next_id += 1
            chain_ids.append(chain_id)
            last_by_shape[shape] = (chain_id, query, row["time"])
        return pd.Series(chain_ids, index=frame.index, name="chain_id")

    return (assign_chains,)


@app.cell
def chain_build(assign_chains, chain_gap, df, mo, pd):
    chains = df.assign(chain_id=assign_chains(df, pd.Timedelta(seconds=chain_gap.value)))
    _by_chain = chains.groupby("chain_id", sort=False)
    chains = chains.assign(
        chain_length=_by_chain["query"].transform("size"),
        position_in_chain=_by_chain.cumcount() + 1,
        final_query=_by_chain["query"].transform("last"),
        longest_query=_by_chain["query"].transform(lambda s: max(s, key=len)),
        chain_started_at=_by_chain["time"].transform("first"),
        chain_solr_wait_ms=_by_chain["solr_wait_ms"].transform("sum"),
    )

    _multi = chains[chains["chain_length"] > 1]
    mo.md(f"""
    - **Chains inferred:** {chains['chain_id'].nunique():,} from {len(chains):,} lookups
      (gap = {chain_gap.value}s)
    - **Multi-keystroke chains:** {_multi['chain_id'].nunique():,}
      ({len(_multi):,} lookups, {len(_multi) / len(chains) * 100:.0f}% of traffic)
    - **Longest chain:** {int(chains['chain_length'].max())} lookups
    - **Solr wait per completed chain:** median
      {_by_chain['solr_wait_ms'].sum().median():,.0f} ms, p95
      {_by_chain['solr_wait_ms'].sum().quantile(0.95):,.0f} ms
    """)
    return (chains,)


@app.cell
def chain_examples(chains):
    # The longest inferred chains, rendered as the sequence the user typed. Useful
    # for eyeballing whether the heuristic is joining sensible things.
    chain_examples = (
        chains[chains["chain_length"] > 1]
        .groupby("chain_id", sort=False)
        .agg(
            started_at=("time", "first"),
            keystrokes=("query", "size"),
            typed=("query", lambda s: " → ".join(s)),
            final_query=("final_query", "first"),
            longest_query=("longest_query", "first"),
            limit=("limit", "first"),
            total_solr_wait_ms=("solr_wait_ms", "sum"),
        )
        .sort_values(["keystrokes", "total_solr_wait_ms"], ascending=False)
        .reset_index(drop=True)
    )
    chain_examples
    return


@app.cell
def chain_csv_header(mo):
    mo.md(r"""
    ## CSV export

    One row per autocomplete lookup, with the inferred final search term attached.
    The four columns asked for are `query`, `time`, `solr_wait_ms` and
    `final_query`; the rest are there to let a reader judge how much to trust the
    chain inference (`chain_length`, `position_in_chain`) and to reproduce the
    request (`limit`).
    """)
    return


@app.cell
def chain_csv_export(NOTEBOOK_DIR, chains, df, mo):
    OUTPUT_DIR = NOTEBOOK_DIR / "output"
    OUTPUT_DIR.mkdir(exist_ok=True)

    autocomplete_csv = chains[
        [
            "query",              # the autocomplete term as typed
            "time",               # when the lookup was issued
            "solr_wait_ms",       # how long NameRes waited on Solr
            "final_query",        # last query in the inferred typing chain
            "longest_query",      # longest query in the chain (survives backspacing)
            "took_ms",
            "chain_id",
            "position_in_chain",
            "chain_length",
            "limit",
            "query_length",
            "slow_query",
            "source_file",
        ]
    ].copy()

    autocomplete_csv_path = OUTPUT_DIR / (
        f"nameres_autocomplete_terms_"
        f"{df['time'].min():%Y-%m-%d}_to_{df['time'].max():%Y-%m-%d}.csv"
    )
    _csv_text = autocomplete_csv.to_csv(index=False)
    autocomplete_csv_path.write_text(_csv_text)

    mo.vstack([
        mo.md(
            f"Wrote **{len(autocomplete_csv):,}** rows to "
            f"`{autocomplete_csv_path}` ({len(_csv_text) / 1e3:.0f} kB)."
        ),
        mo.download(
            data=_csv_text.encode("utf-8"),
            filename=autocomplete_csv_path.name,
            mimetype="text/csv",
            label="Download autocomplete terms CSV",
        ),
        autocomplete_csv.head(25),
    ])
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
    real production autocomplete queries.

    Every case here has `autocomplete=True`; a replay harness must not drop that
    flag, since it is the whole difference between this workload and a plain lookup.
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
def bench_export(
    NOTEBOOK_DIR,
    benchmark_cases,
    df,
    json,
    log_file_summary,
    mo,
):
    BENCHMARK_DIR = NOTEBOOK_DIR / "benchmark"
    BENCHMARK_DIR.mkdir(exist_ok=True)
    # Name the export after the window the source logs actually cover, so two runs
    # over different log sets do not overwrite each other.
    benchmark_path = BENCHMARK_DIR / (
        f"nameres_autocomplete_solr_benchmark_"
        f"{df['time'].min():%Y-%m-%d}_to_{df['time'].max():%Y-%m-%d}.json"
    )

    benchmark_payload = {
        "mode": "autocomplete",
        "source_logs": sorted(log_file_summary["file"]),
        "log_span": [str(df["time"].min()), str(df["time"].max())],
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


@app.cell(hide_code=True)
def next_steps(mo):
    mo.md(r"""
    # Next steps

    This notebook characterizes **autocomplete** traffic against the **Solr**
    backend and emits both a replayable benchmark and a per-lookup CSV. To turn it
    into a Solr-vs-ElasticSearch comparison, the planned follow-up work is:

    1. **Replay harness.** Issue each benchmark case (from
       `benchmark/nameres_autocomplete_solr_benchmark_*.json`) against a live NameRes
       endpoint — once against the Solr backend, once against the ElasticSearch
       backend — recording measured latency per case. Reuse `CachedNameRes`
       (`src/babel_validation/services/nameres.py`) for the API calls.

    2. **Latency comparison.** Join the replayed ES/Solr latencies back to each
       case's `baseline_solr` to produce per-case and aggregate speedup/regression
       tables and charts. Watch the pathological cases first: short prefixes at
       `limit=100`.

    3. **Result-quality parity, not just speed.** The current benchmark compares
       latency only. A fuller benchmark should also compare the **result sets** each
       backend returns (do the top-N hits match?), so an ES speedup isn't bought at
       the cost of relevance. Autocomplete makes this sharper: the chain data says
       what the user *ended up* searching for, so we can ask whether the right answer
       was already in the top N several keystrokes earlier.

    4. **Chain-level metrics.** The typing chains are currently descriptive. The
       metric a user actually feels is the total Solr wait across a whole chain, and
       the slowest single keystroke in it — worth promoting to a headline comparison
       between backends.

    5. **Bring back non-autocomplete analysis.** Exact-match lookups were split out
       of this notebook because mixing the two populations made every aggregate a
       weighted average of two things that behave nothing alike (p95 Solr wait
       ~2.8 s vs ~43 ms). They deserve their own notebook over the general
       `data/log-analysis/nameres-*` exports, sharing this one's parser.

    6. **De-duplicate overlapping exports.** `assert_no_overlapping_spans` currently
       refuses overlapping windows outright. Logs Insights records carry no ID, so
       de-duplication would have to key on something like (`@timestamp`,
       `pod_name`, log line).

    7. **Extra breakdowns.** Latency by `biolink_types` filter set, by prefix/taxa
       filters, and by pod / image tag, to check for per-instance or per-version
       effects. `pod_name` and `image_tag` are parsed onto `entries` but kept off
       `df`, since `df` is rendered in full into the shared HTML export and nothing
       here analyses them — start from `entries`. Comparing NameRes releases (say
       v1.5.2 against v1.7.0) is the case that would make `image_tag` earn its
       place.
    """)
    return


if __name__ == "__main__":
    app.run()
