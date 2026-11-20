import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def imports():
    import marimo as mo
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from matplotlib.patches import Patch

    from src.babel_validation.tools import nodenorm_logs

    return LogNorm, Patch, mo, nodenorm_logs, np, pd, plt


@app.cell(hide_code=True)
def intro(mo):
    mo.md(r"""
    # NodeNorm log analysis

    Since [NodeNormalization#312](https://github.com/TranslatorSRI/NodeNormalization/pull/312), NodeNorm logs one line for every `get_normalized_nodes` call:

    ```
    2025-06-18 07:26:30,635 | INFO | normalizer:get_normalized_nodes | Normalized 1 nodes in 1.21 ms with arguments (curies=['UMLS:C0132098'], conflate_gene_protein=True, conflate_chemical_drug=True, include_descriptions=False, include_individual_types=True)
    ```

    This notebook reads every log export it finds and reports on how NodeNorm performed.

    **What the time is.** It is the time spent inside the normalizer for one call: looking the CURIEs up and building the response. It does not include time queued in the web server, serialising the response, or the network. So these numbers are a floor on what a client saw.

    **What the logs cannot say.** Nothing here records who called, how many of the CURIEs were found, or the HTTP status. Requests to other endpoints are not logged at all. The missing count of CURIEs found matters: identifiers NodeNorm does not know appear to be answered much faster than ones it does, so two requests of the same size can differ a hundredfold.

    All times are UTC.
    """)
    return


@app.cell(hide_code=True)
def files_header(mo):
    mo.md(r"""
    ## Files analysed

    Everything under `data/log-analysis/nodenorm/` at the repository root is read, including subdirectories. That directory is gitignored, because a month of logs is hundreds of megabytes. To analyse more logs, put the files there and re-run the notebook; nothing here names a file.

    The reader understands Loki exports (`loki_query_results_*.json`), loose or inside a `.tar.gz`. Anything else is listed below as skipped, with the reason. Log entries that appear twice, in one file or across files, are counted once.
    """)
    return


@app.cell
def log_dir(mo):
    # Anchored on the notebook's directory rather than the cwd, which is wherever marimo was launched from.
    LOG_DIR = mo.notebook_dir().parents[1] / "data" / "log-analysis" / "nodenorm"
    EXPORT_DIR = mo.notebook_dir() / "exports"
    return EXPORT_DIR, LOG_DIR


@app.cell
def load(LOG_DIR, mo, nodenorm_logs):
    with mo.status.spinner(title=f"Reading NodeNorm logs from {LOG_DIR}"):
        loaded = nodenorm_logs.load_logs(LOG_DIR)

    mo.stop(
        not loaded.columns["time"],
        mo.callout(
            mo.md(f"No NodeNorm requests were found under `{LOG_DIR}` ({len(loaded.files)} files seen). See the README beside this notebook for where to get the logs."),
            kind="danger",
        ),
    )
    return (loaded,)


@app.cell
def helpers(np):
    OPTION_FLAGS = {
        "conflate_gene_protein": "gene/protein conflation",
        "conflate_chemical_drug": "drug/chemical conflation",
        "include_descriptions": "descriptions",
        "include_individual_types": "individual types",
    }
    QUANTILES = {"p50": 0.5, "p90": 0.9, "p99": 0.99}
    QUANTILE_STYLES = {"p50": ("#1f77b4", "o"), "p90": ("#ff7f0e", "s"), "p99": ("#d62728", "^")}


    def quantile_table(grouped, column="time_taken_ms"):
        """One row per group: how many requests, and the p50/p90/p99 of `column`."""
        table = grouped[column].quantile(list(QUANTILES.values())).unstack()
        table.columns = list(QUANTILES)
        table.insert(0, "requests", grouped.size())
        return table


    def safe_label(text):
        """Text from a log file, made safe to use as a chart label.

        repr() escapes control characters, and matplotlib would otherwise read a `$` as the
        start of a formula and fail to draw the chart.
        """
        return repr(str(text))[1:-1].replace("$", r"\$")


    def log_bins(values, per_decade=5):
        """Bin edges evenly spaced on a log scale, covering `values`."""
        top = np.log10(max(values.max(), 10))
        return np.unique(np.round(10 ** np.arange(0, top + 1 / per_decade, 1 / per_decade)))

    return (
        OPTION_FLAGS,
        QUANTILES,
        QUANTILE_STYLES,
        log_bins,
        quantile_table,
        safe_label,
    )


@app.cell
def all_requests(OPTION_FLAGS, loaded, np, pd):
    all_requests = pd.DataFrame(loaded.columns)
    all_requests["time"] = pd.to_datetime(all_requests["time"], format="%Y-%m-%d %H:%M:%S.%f")
    all_requests["ms_per_curie"] = all_requests["time_taken_ms"] / all_requests["curie_count"]
    all_requests["first_prefix"] = all_requests["first_prefix"].replace("", "(no prefix)")
    for _column in ["options", "pod", "node_name", "namespace", "first_prefix", "source"]:
        all_requests[_column] = all_requests[_column].astype("category")

    # One boolean column per option, read off the handful of distinct option strings rather
    # than off every row. A line cut short by the log shipper has no options; it counts as
    # False for all of them.
    _options = all_requests["options"].cat
    for _flag in OPTION_FLAGS:
        _is_set = np.array([f"{_flag}=True" in _text for _text in _options.categories] + [False])
        all_requests[_flag] = _is_set[_options.codes]
    all_requests["options_label"] = (
        _options.rename_categories(
            lambda _text: ", ".join(_label for _flag, _label in OPTION_FLAGS.items() if f"{_flag}=True" in _text)
            or "no options"
        )
        if _options.categories.size
        else "no options"
    )

    all_requests = all_requests.sort_values("time", ignore_index=True)
    return (all_requests,)


@app.cell
def files_table(all_requests, loaded, mo, pd):
    files_table = pd.DataFrame(
        [
            {
                "file": _f.path,
                "status": _f.status,
                "format": _f.format,
                "size (MB)": round(_f.size_bytes / 1e6, 1),
                "exports read": _f.members_read,
                "requests": _f.requests,
                "CURIEs": _f.curies,
                "first request": _f.first_request[:19],
                "last request": _f.last_request[:19],
                "hours queried": round(_f.hours_queried, 1),
                "duplicates dropped": _f.duplicates,
                "other lines": _f.other_lines,
                "notes": _f.notes,
            }
            for _f in loaded.files
        ]
    )
    _not_loaded = files_table[files_table["status"] != "loaded"]

    mo.vstack(
        [
            mo.md(
                f"**{len(all_requests):,} requests** naming **{all_requests['curie_count'].sum():,} CURIEs**, "
                f"from {(files_table['status'] == 'loaded').sum()} of {len(files_table)} files, "
                f"between {all_requests['time'].min():%Y-%m-%d %H:%M} and {all_requests['time'].max():%Y-%m-%d %H:%M} UTC."
            ),
            mo.callout(
                mo.md(f"**{len(_not_loaded)} file(s) were not loaded:** " + ", ".join(f"`{_p}`" for _p in _not_loaded["file"])),
                kind="warn",
            )
            if len(_not_loaded)
            else None,
            mo.ui.table(files_table, selection=None, pagination=False),
            mo.md(
                "*Hours queried* is the time the export's own queries say they cover, which is how "
                "the coverage chart below tells a quiet hour from one that was never downloaded. "
                "*Other lines* are log lines that are not `get_normalized_nodes` calls."
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def export_header(mo):
    mo.md(r"""
    ### Export the requests as CSV

    For anyone who wants to re-analyse these requests without parsing the log exports again. One row per request, everything loaded above (the filters below do not apply):

    | Column | Meaning |
    |---|---|
    | `time` | When NodeNorm logged the request, UTC |
    | `curie_count` | CURIEs in the request |
    | `time_taken_ms` | Time inside the normalizer, in milliseconds |
    | `ms_per_curie` | `time_taken_ms / curie_count` |
    | `conflate_gene_protein`, `conflate_chemical_drug`, `include_descriptions`, `include_individual_types` | The request's options |
    | `first_prefix` | Prefix of the first CURIE; `(no prefix)` if it had none. One starting with `=`, `+`, `-` or `@` gets a leading `'`, so that a spreadsheet does not run it as a formula |
    | `namespace`, `node_name`, `pod` | Where it ran: Kubernetes namespace, node and pod |
    | `source` | The file it was read from |

    The CURIEs themselves are left out: there are tens of millions. The file goes in `exports/` beside this notebook, which is gitignored; it names pods and nodes, so share it the way you would share the logs.
    """)
    return


@app.cell
def export_button(mo):
    export_button = mo.ui.run_button(label="Write the CSV")
    export_button
    return (export_button,)


@app.cell
def export_csv(EXPORT_DIR, OPTION_FLAGS, all_requests, export_button, mo):
    mo.stop(not export_button.value, mo.md("*Not written in this run.*"))

    EXPORT_COLUMNS = [
        "time", "curie_count", "time_taken_ms", "ms_per_curie", *OPTION_FLAGS,
        "first_prefix", "namespace", "node_name", "pod", "source",
    ]  # fmt: skip
    EXPORT_DIR.mkdir(exist_ok=True)
    _path = EXPORT_DIR / (
        f"nodenorm-requests-{all_requests['time'].min():%Y%m%d}-to-{all_requests['time'].max():%Y%m%d}.generated.csv.gz"
    )

    # A prefix is whatever a caller typed before the first colon, and a spreadsheet runs a
    # cell that starts with one of these characters as a formula. A leading apostrophe makes
    # it text. Every other column is a number, a flag, or a name Kubernetes or we chose.
    _as_text = {
        _p: "'" + _p if _p[:1] in ("=", "+", "-", "@") or _p[:1].isspace() else _p
        for _p in all_requests["first_prefix"].cat.categories
    }
    with mo.status.spinner(title=f"Writing {_path.name}"):
        all_requests[EXPORT_COLUMNS].assign(
            first_prefix=all_requests["first_prefix"].astype(object).map(_as_text)
        ).to_csv(_path, index=False, date_format="%Y-%m-%dT%H:%M:%S.%fZ")

    mo.md(f"Wrote {len(all_requests):,} rows to `{_path}` ({_path.stat().st_size / 1e6:.0f} MB).")
    return


@app.cell(hide_code=True)
def filters_header(mo):
    mo.md(r"""
    ## Filters

    Everything below is drawn from the requests that pass these filters.
    """)
    return


@app.cell
def filters(all_requests, mo):
    date_filter = mo.ui.date_range(
        start=all_requests["time"].min().date(),
        stop=all_requests["time"].max().date(),
        label="Dates (UTC)",
    )
    namespace_filter = mo.ui.multiselect(
        options=list(all_requests["namespace"].cat.categories),
        value=list(all_requests["namespace"].cat.categories),
        label="Kubernetes namespace",
    )
    mo.hstack([date_filter, namespace_filter], justify="start", gap=2)
    return date_filter, namespace_filter


@app.cell
def filtered(
    all_requests,
    date_filter,
    loaded,
    mo,
    namespace_filter,
    nodenorm_logs,
    pd,
):
    _start, _stop = (pd.Timestamp(_d) for _d in date_filter.value)
    df = all_requests[
        (all_requests["time"] >= _start)
        & (all_requests["time"] < _stop + pd.Timedelta(days=1))
        & all_requests["namespace"].isin(namespace_filter.value)
    ]
    mo.stop(df.empty, mo.callout(mo.md("No requests match the filters."), kind="warn"))

    # A request for one CURIE is the cleanest thing to compare across options, nodes and
    # prefixes: its time is not a mix of batch sizes.
    single = df[df["curie_count"] == 1]

    # Every hour that some export's query covered, whether or not it returned anything.
    _hours = set()
    for _start_ns, _end_ns in nodenorm_logs.merge_windows(_w for _f in loaded.files for _w in _f.windows):
        _hours.update(range(_start_ns // nodenorm_logs.NS_PER_HOUR, (_end_ns - 1) // nodenorm_logs.NS_PER_HOUR + 1))
    covered_hours = pd.to_datetime(sorted(_hours), unit="h")
    covered_hours = covered_hours[(covered_hours >= _start) & (covered_hours < _stop + pd.Timedelta(days=1))]

    # Requests in each covered hour, zeros included.
    hourly_requests = df.groupby(df["time"].dt.floor("h")).size().reindex(covered_hours, fill_value=0)

    mo.md(f"**{len(df):,} requests** selected, across {len(covered_hours):,} hours of logs.")
    return covered_hours, df, hourly_requests, single


@app.cell(hide_code=True)
def coverage_header(mo):
    mo.md(r"""
    ## Coverage

    Which hours the logs cover, and how busy each was. Grey hours were not downloaded: no export queried them. White hours were queried and had no requests. Read every chart below with this in mind: a gap in a time series is usually a gap in the downloads.
    """)
    return


@app.cell
def coverage(LogNorm, Patch, covered_hours, hourly_requests, np, pd, plt):
    _days = pd.date_range(covered_hours.min().floor("D"), covered_hours.max().floor("D"), freq="D")
    _grid = np.full((24, len(_days)), np.nan)
    _grid[covered_hours.hour, (covered_hours.floor("D") - _days[0]).days] = hourly_requests.to_numpy()

    _fig, _ax = plt.subplots(figsize=(14, 4.5))
    _ax.set_facecolor("#cccccc")
    _cmap = plt.get_cmap("viridis").copy()
    _cmap.set_bad(alpha=0)
    _ax.imshow(np.where(_grid == 0, 1.0, np.nan), cmap="gray", vmin=0, vmax=1, aspect="auto", origin="lower")
    _image = _ax.imshow(
        np.where(_grid > 0, _grid, np.nan), cmap=_cmap, norm=LogNorm(vmin=1, vmax=max(np.nanmax(_grid), 10)),
        aspect="auto", origin="lower",
    )  # fmt: skip
    _ticks = np.arange(0, len(_days), max(1, len(_days) // 15))
    _ax.set_xticks(_ticks, [_days[_i].strftime("%b %d") for _i in _ticks], rotation=45, ha="right")
    _ax.set_yticks(range(0, 24, 3))
    _ax.set_ylabel("Hour of day (UTC)")
    _ax.set_title(f"Requests per hour ({len(covered_hours):,} of {len(_days) * 24:,} hours covered)")
    _ax.legend(
        handles=[Patch(facecolor="#cccccc", label="not downloaded"), Patch(facecolor="white", edgecolor="black", label="no requests")],
        loc="upper left", bbox_to_anchor=(1.12, 1), frameon=False,
    )  # fmt: skip
    _fig.colorbar(_image, ax=_ax, label="Requests in the hour", pad=0.01)
    _fig.tight_layout()
    _fig
    return


@app.cell(hide_code=True)
def headline_header(mo):
    mo.md(r"""
    ## Headline numbers
    """)
    return


@app.cell
def headline(df, hourly_requests, mo, nodenorm_logs):
    _ms = df["time_taken_ms"]
    _p50, _p90, _p99, _p999 = _ms.quantile([0.5, 0.9, 0.99, 0.999])
    _curies = df["curie_count"].sum()
    _slow = (_ms >= nodenorm_logs.SLOW_REQUEST_MS).sum()

    mo.vstack(
        [
            mo.hstack(
                [
                    mo.stat(f"{len(df):,}", label="Requests", caption=f"busiest hour: {hourly_requests.max():,}"),
                    mo.stat(f"{_curies:,}", label="CURIEs", caption=f"{_curies / len(df):.1f} per request on average"),
                    mo.stat(f"{(df['curie_count'] == 1).mean():.0%}", label="Single-CURIE requests", caption=f"largest batch: {df['curie_count'].max():,}"),
                    mo.stat(f"{df['pod'].nunique():,}", label="Pods", caption=f"on {df['node_name'].nunique()} nodes"),
                ],
                widths="equal",
            ),
            mo.hstack(
                [
                    mo.stat(f"{_p50:.2f} ms", label="Median request"),
                    mo.stat(f"{_p90:.1f} ms", label="p90"),
                    mo.stat(f"{_p99:.0f} ms", label="p99"),
                    mo.stat(f"{_p999:,.0f} ms", label="p99.9", caption=f"slowest: {_ms.max() / 1000:.1f} s"),
                    mo.stat(f"{_slow:,}", label=f"Requests over {nodenorm_logs.SLOW_REQUEST_MS / 1000:.0f} s", caption=f"{_slow / len(df):.3%} of requests"),
                    mo.stat(f"{_curies / (_ms.sum() / 1000):,.0f}", label="CURIEs per second", caption="of normalizer time"),
                ],
                widths="equal",
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def over_time_header(mo):
    mo.md(r"""
    ## Latency over time

    Daily percentiles of the time per request, and per CURIE. A step here that is not matched by a change in traffic is the thing to look for: it would point at a deployment, a data load, or the Redis backend. Per-CURIE time is the fairer comparison between days, because a day of large batches has slow requests without being a slow day.
    """)
    return


@app.cell
def over_time(QUANTILE_STYLES, df, pd, plt, quantile_table):
    _by_day = df.groupby(df["time"].dt.floor("D"))
    _days = pd.date_range(df["time"].min().floor("D"), df["time"].max().floor("D"), freq="D")
    _per_request = quantile_table(_by_day).reindex(_days)
    _per_curie = quantile_table(_by_day, "ms_per_curie").reindex(_days)
    _daily_curies = _by_day["curie_count"].sum().reindex(_days)

    _fig, _axes = plt.subplots(4, 1, figsize=(14, 11), sharex=True)
    for _ax, _table, _title in [
        (_axes[0], _per_request, "Time per request (ms)"),
        (_axes[1], _per_curie, "Time per CURIE (ms)"),
    ]:
        for _name, (_colour, _marker) in QUANTILE_STYLES.items():
            _ax.plot(_table.index, _table[_name], color=_colour, marker=_marker, markersize=3, linewidth=1, label=_name)
        _ax.set_yscale("log")
        _ax.set_ylabel(_title)
        _ax.grid(True, which="both", alpha=0.3)
        _ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1), frameon=False)
    _axes[2].bar(_days, _per_request["requests"], width=0.9, color="#7f7f7f")
    _axes[2].set_ylabel("Requests per day")
    _axes[3].bar(_days, _daily_curies, width=0.9, color="#7f7f7f")
    _axes[3].set_ylabel("CURIEs per day")
    for _ax in _axes[2:]:
        _ax.set_yscale("log")
        _ax.grid(True, axis="y", alpha=0.3)
    _axes[0].set_title("Daily latency percentiles and traffic (days with no logs are left blank)")
    _fig.autofmt_xdate()
    _fig.tight_layout()
    _fig
    return


@app.cell(hide_code=True)
def batch_header(mo):
    mo.md(r"""
    ## Batch size

    How many CURIEs clients send at once, and what that does to the time. The first table shows where the work is: most requests are small, but most CURIEs, and most of the normalizer's time, can come from the few large ones.

    Requests whose first identifier has no prefix (bare numbers, gene symbols) are drawn separately in the second chart. NodeNorm answers those in about a millisecond whatever their size, presumably because there is nothing to look up, and mixed in with the rest they make batches look faster than they are.
    """)
    return


@app.cell
def batch_shares(QUANTILES, df, mo, np, pd, plt, quantile_table):
    _buckets = pd.cut(
        df["curie_count"],
        [0, 1, 10, 100, 1000, 10000, np.inf],
        labels=["1", "2 to 10", "11 to 100", "101 to 1,000", "1,001 to 10,000", "over 10,000"],
    )
    _grouped = df.groupby(_buckets, observed=False)
    batch_table = quantile_table(_grouped).rename(columns={_q: f"{_q} (ms)" for _q in QUANTILES})
    batch_table["median ms per CURIE"] = _grouped["ms_per_curie"].median()
    batch_table.insert(1, "% of requests", 100 * batch_table["requests"] / len(df))
    batch_table.insert(2, "% of CURIEs", 100 * _grouped["curie_count"].sum() / df["curie_count"].sum())
    batch_table.insert(3, "% of time", 100 * _grouped["time_taken_ms"].sum() / df["time_taken_ms"].sum())
    batch_table.index.name = "CURIEs in request"

    _fig, _ax = plt.subplots(figsize=(10, 3.5))
    batch_table[["% of requests", "% of CURIEs", "% of time"]].plot.bar(ax=_ax, width=0.8, color=["#1f77b4", "#ff7f0e", "#2ca02c"])
    _ax.set_ylabel("Share (%)")
    _ax.set_title("Share of requests, CURIEs and normalizer time, by batch size")
    _ax.tick_params(axis="x", rotation=0)
    _ax.grid(True, axis="y", alpha=0.3)
    _fig.tight_layout()

    mo.vstack([_fig, mo.ui.table(batch_table.round(2).reset_index(), selection=None, pagination=False)])
    return


@app.cell
def batch_latency(df, log_bins, mo, pd, plt):
    _edges = log_bins(df["curie_count"])
    _has_prefix = df["first_prefix"] != "(no prefix)"

    _fig, _axes = plt.subplots(1, 2, figsize=(14, 5))
    for _mask, _label, _colour in [
        (_has_prefix, "first identifier has a prefix", "#1f77b4"),
        (~_has_prefix, "first identifier has no prefix", "#ff7f0e"),
    ]:
        _part = df[_mask]
        if _part.empty:
            continue
        _grouped = _part.groupby(pd.cut(_part["curie_count"], _edges, include_lowest=True), observed=True)
        _enough = _grouped.size() >= 20  # too few requests in a bin makes its percentiles meaningless
        _x = _grouped["curie_count"].median()[_enough]
        for _ax, _column in zip(_axes, ["time_taken_ms", "ms_per_curie"]):
            _q = _grouped[_column].quantile([0.1, 0.5, 0.9]).unstack()[_enough]
            _ax.fill_between(_x, _q[0.1], _q[0.9], color=_colour, alpha=0.2)
            _ax.plot(_x, _q[0.5], color=_colour, marker="o", markersize=3, label=_label)
    for _ax, _ylabel, _title in [
        (_axes[0], "Time per request (ms)", "Larger batches take longer..."),
        (_axes[1], "Time per CURIE (ms)", "...but each CURIE in them is cheaper"),
    ]:
        _ax.set_xscale("log")
        _ax.set_yscale("log")
        _ax.set_xlabel("CURIEs in request")
        _ax.set_ylabel(_ylabel)
        _ax.set_title(_title)
        _ax.grid(True, which="both", alpha=0.3)
        _ax.legend(frameon=False, title="Median, with p10 to p90 shaded")
    _fig.tight_layout()

    _prefixed = df[_has_prefix]
    _single_cost = _prefixed.loc[_prefixed["curie_count"] == 1, "ms_per_curie"].median()
    _batch_cost = _prefixed.loc[_prefixed["curie_count"] >= 100, "ms_per_curie"].median()
    mo.vstack(
        [
            _fig,
            mo.md(
                f"Among requests whose first identifier has a prefix, a CURIE sent on its own costs a median "
                f"**{_single_cost:.2f} ms**, and a CURIE in a batch of 100 or more costs **{_batch_cost:.2f} ms**. "
                f"Bins with fewer than 20 requests are not drawn."
            ),
            mo.md(
                f"The shaded band is wide: at one batch size, times differ by a factor of ten or more. The log "
                f"does not say how many of a request's CURIEs were found, and that is the likeliest cause."
            ),
            mo.md(
                f"**{(~_has_prefix).mean():.1%} of requests**, carrying {df.loc[~_has_prefix, 'curie_count'].sum() / df['curie_count'].sum():.1%} "
                f"of all identifiers sent, start with an identifier that has no prefix. Their median time is "
                f"{df.loc[~_has_prefix, 'time_taken_ms'].median():.2f} ms."
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def options_header(mo):
    mo.md(r"""
    ## Options

    Each request sets four options. The logs do not identify clients, but a client tends to use one combination, so the combinations act as rough fingerprints: a change in the mix over time is a client arriving, leaving or changing its code.

    The table compares single-CURIE requests only, so that the options are not confused with batch size.
    """)
    return


@app.cell
def options(QUANTILES, df, mo, np, plt, quantile_table, single):
    options_table = quantile_table(single.groupby("options_label", observed=True)).rename(
        columns={"requests": "single-CURIE requests", **{_q: f"{_q} (ms)" for _q in QUANTILES}}
    )
    options_table.insert(0, "all requests", df.groupby("options_label", observed=True).size())
    options_table.insert(1, "% of requests", 100 * options_table["all requests"] / len(df))
    options_table = options_table.sort_values("all requests", ascending=False)
    options_table.index.name = "options set"

    _daily = df.groupby([df["time"].dt.floor("D"), "options_label"], observed=True).size().unstack(fill_value=0)
    _daily = _daily[options_table.index[:8]]  # the eight most used; the rest are a sliver
    _share = 100 * _daily.div(df.groupby(df["time"].dt.floor("D")).size(), axis=0)

    _fig, _ax = plt.subplots(figsize=(14, 4.5))
    _bottom = np.zeros(len(_share))
    for _label, _colour in zip(_share.columns, plt.get_cmap("tab10").colors):
        _ax.bar(_share.index, _share[_label], bottom=_bottom, width=0.95, color=_colour, label=_label)
        _bottom += _share[_label].to_numpy()
    _ax.set_ylabel("Share of the day's requests (%)")
    _ax.set_ylim(0, 100)
    _ax.set_title("Which option combinations were in use, day by day")
    _ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, fontsize=8)
    _fig.autofmt_xdate()
    _fig.tight_layout()

    mo.vstack([mo.ui.table(options_table.round(2).reset_index(), selection=None, pagination=False), _fig])
    return


@app.cell(hide_code=True)
def infrastructure_header(mo):
    mo.md(r"""
    ## Infrastructure

    Loki records which pod served each request and which Kubernetes node that pod was on. A node that is slower than the rest on the same kind of request points at the hardware or at a noisy neighbour, not at NodeNorm. Single-CURIE requests only.
    """)
    return


@app.cell
def nodes(
    QUANTILES,
    QUANTILE_STYLES,
    df,
    mo,
    np,
    plt,
    quantile_table,
    safe_label,
    single,
):
    nodes_table = quantile_table(single.groupby("node_name", observed=True)).rename(
        columns={"requests": "single-CURIE requests", **{_q: f"{_q} (ms)" for _q in QUANTILES}}
    )
    nodes_table.insert(0, "pods", df.groupby("node_name", observed=True)["pod"].nunique())
    nodes_table.insert(1, "all requests", df.groupby("node_name", observed=True).size())
    nodes_table = nodes_table.sort_values("p50 (ms)")
    nodes_table.index.name = "node"

    _fig, _ax = plt.subplots(figsize=(10, 0.35 * len(nodes_table) + 1.5))
    _y = np.arange(len(nodes_table))
    for _name, (_colour, _marker) in QUANTILE_STYLES.items():
        _ax.scatter(nodes_table[f"{_name} (ms)"], _y, color=_colour, marker=_marker, label=_name, zorder=3)
    _ax.hlines(_y, nodes_table["p50 (ms)"], nodes_table["p99 (ms)"], color="#bbbbbb", zorder=2)
    _ax.set_yticks(_y, [safe_label(_n) for _n in nodes_table.index])
    _ax.set_xscale("log")
    _ax.set_xlabel("Time for a single-CURIE request (ms)")
    _ax.set_title("Latency by Kubernetes node")
    _ax.grid(True, axis="x", which="both", alpha=0.3)
    _ax.legend(frameon=False, ncols=3)
    _fig.tight_layout()

    mo.vstack([_fig, mo.ui.table(nodes_table.round(2).reset_index(), selection=None, pagination=False)])
    return


@app.cell
def pods(Patch, df, mo, np, pd, plt, safe_label):
    pods_table = df.groupby("pod", observed=True).agg(
        node=("node_name", "first"), first_request=("time", "min"), last_request=("time", "max"), requests=("time", "size")
    )
    pods_table = pods_table.sort_values("first_request")
    _nodes = sorted(pods_table["node"].unique())
    _colours = dict(zip(_nodes, plt.get_cmap("tab20").colors))

    _fig, _ax = plt.subplots(figsize=(14, max(4, 0.045 * len(pods_table) + 1.5)))
    _ax.hlines(
        np.arange(len(pods_table)), pods_table["first_request"], pods_table["last_request"],
        colors=[_colours[_n] for _n in pods_table["node"]], linewidth=2,
    )  # fmt: skip
    _ax.set_ylabel("Pod (in order of first request)")
    _ax.set_title(f"When each of the {len(pods_table)} pods was serving requests")
    _ax.legend(
        handles=[Patch(color=_colours[_n], label=safe_label(_n)) for _n in _nodes],
        loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, fontsize=8,
    )  # fmt: skip
    _ax.grid(True, axis="x", alpha=0.3)
    _fig.autofmt_xdate()
    _fig.tight_layout()

    _lifetime = pods_table["last_request"] - pods_table["first_request"]
    mo.vstack(
        [
            _fig,
            mo.md(
                f"Each line runs from a pod's first logged request to its last. A new pod is a restart or a "
                f"redeployment; a pod's name changes each time. The median pod was seen for "
                f"**{_lifetime.median() / pd.Timedelta(hours=1):.1f} hours**, the longest for "
                f"{_lifetime.max() / pd.Timedelta(days=1):.1f} days. Gaps in the downloads cut lines short, so "
                f"compare against the coverage chart before reading a short line as a crash."
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def load_header(mo):
    mo.md(r"""
    ## Does latency rise with load?

    Each pod is one process, so what a request competes with is the other work its own pod is doing. Here every single-CURIE request is placed by how many CURIEs its pod handled in the same minute. A flat line means the pod had headroom; a line that climbs to the right shows where requests start waiting on each other.
    """)
    return


@app.cell
def load_vs_latency(
    QUANTILE_STYLES,
    df,
    log_bins,
    pd,
    plt,
    quantile_table,
    single,
):
    _minute = df["time"].dt.floor("min")
    _pod_load = df.groupby([df["pod"], _minute], observed=True)["curie_count"].transform("sum")
    _single_load = _pod_load[single.index]
    _grouped = single.groupby(pd.cut(_single_load, log_bins(_single_load, per_decade=4), include_lowest=True), observed=True)
    load_table = quantile_table(_grouped)
    load_table.insert(0, "CURIEs in the pod's minute", _single_load.groupby(_grouped.ngroup()).median().to_numpy())
    _drawn = load_table[load_table["requests"] >= 20]

    _fig, _axes = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True, height_ratios=[3, 1])
    for _name, (_colour, _marker) in QUANTILE_STYLES.items():
        _axes[0].plot(_drawn["CURIEs in the pod's minute"], _drawn[_name], color=_colour, marker=_marker, markersize=4, label=_name)
    _axes[0].set_xscale("log")
    _axes[0].set_yscale("log")
    _axes[0].set_ylabel("Time for a single-CURIE request (ms)")
    _axes[0].set_title("Single-CURIE latency against how busy the pod was")
    _axes[0].grid(True, which="both", alpha=0.3)
    _axes[0].legend(frameon=False, ncols=3)
    _axes[1].bar(_drawn["CURIEs in the pod's minute"], _drawn["requests"], width=0.35 * _drawn["CURIEs in the pod's minute"], color="#7f7f7f")
    _axes[1].set_yscale("log")
    _axes[1].set_ylabel("Requests")
    _axes[1].set_xlabel("CURIEs the same pod handled in that minute")
    _axes[1].grid(True, which="both", alpha=0.3)
    _fig.tight_layout()
    _fig
    return


@app.cell(hide_code=True)
def when_header(mo):
    mo.md(r"""
    ## When traffic arrives

    Average requests per hour, by day of the week and hour of the day, counting only hours the logs cover. Regular blocks are scheduled jobs; a working-hours pattern is people.
    """)
    return


@app.cell
def when(LogNorm, hourly_requests, plt):
    _weekly = hourly_requests.groupby([hourly_requests.index.day_of_week, hourly_requests.index.hour]).mean().unstack()
    _weekly = _weekly.reindex(index=range(7), columns=range(24))

    _fig, _ax = plt.subplots(figsize=(14, 3.8))
    _cmap = plt.get_cmap("viridis").copy()
    _cmap.set_bad("#cccccc")
    _image = _ax.imshow(
        _weekly.where(_weekly > 0), cmap=_cmap, aspect="auto",
        norm=LogNorm(vmin=max(_weekly[_weekly > 0].min().min(), 1), vmax=max(_weekly.max().max(), 10)),
    )  # fmt: skip
    _ax.set_yticks(range(7), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    _ax.set_xticks(range(24))
    _ax.set_xlabel("Hour of day (UTC)")
    _ax.set_title("Average requests per hour (grey: no requests, or no logs for that slot)")
    _fig.colorbar(_image, ax=_ax, label="Requests per hour", pad=0.01)
    _fig.tight_layout()
    _fig
    return


@app.cell(hide_code=True)
def prefixes_header(mo):
    mo.md(r"""
    ## Prefixes

    What is being looked up, by the prefix of the CURIE, and whether some prefixes are slower than others. Single-CURIE requests only, so each time belongs to one identifier.

    Identifiers with no prefix at all show up as `(no prefix)`, and malformed ones (a URL, a lower-case prefix) appear under whatever came before their first colon. NodeNorm cannot normalize those, so they are wasted calls that a client could avoid.
    """)
    return


@app.cell
def prefixes(
    QUANTILES,
    QUANTILE_STYLES,
    mo,
    np,
    plt,
    quantile_table,
    safe_label,
    single,
):
    prefix_table = quantile_table(single.groupby("first_prefix", observed=True)).rename(
        columns={"requests": "single-CURIE requests", **{_q: f"{_q} (ms)" for _q in QUANTILES}}
    )
    prefix_table.insert(1, "% of single-CURIE requests", 100 * prefix_table["single-CURIE requests"] / len(single))
    prefix_table = prefix_table.sort_values("single-CURIE requests", ascending=False)
    prefix_table.index.name = "prefix"
    _top = prefix_table.head(25).iloc[::-1]

    _fig, _axes = plt.subplots(1, 2, figsize=(14, 0.3 * len(_top) + 1.5), sharey=True)
    _y = np.arange(len(_top))
    _axes[0].barh(_y, _top["single-CURIE requests"], color="#7f7f7f")
    _axes[0].set_yticks(_y, [safe_label(_p) for _p in _top.index])
    _axes[0].set_xscale("log")
    _axes[0].set_xlabel("Single-CURIE requests")
    _axes[0].set_title(f"The {len(_top)} most requested prefixes")
    for _name, (_colour, _marker) in QUANTILE_STYLES.items():
        _axes[1].scatter(_top[f"{_name} (ms)"], _y, color=_colour, marker=_marker, label=_name, zorder=3)
    _axes[1].hlines(_y, _top["p50 (ms)"], _top["p99 (ms)"], color="#bbbbbb", zorder=2)
    _axes[1].set_xscale("log")
    _axes[1].set_xlabel("Time for a single-CURIE request (ms)")
    _axes[1].set_title("Their latency")
    _axes[1].legend(frameon=False, ncols=3)
    for _ax in _axes:
        _ax.grid(True, axis="x", which="both", alpha=0.3)
    _fig.tight_layout()

    mo.vstack(
        [
            _fig,
            mo.md(f"All {len(prefix_table):,} prefixes seen in single-CURIE requests:"),
            mo.ui.table(prefix_table.round(2).reset_index(), selection=None, page_size=15),
        ]
    )
    return


@app.cell(hide_code=True)
def slow_header(mo):
    mo.md(r"""
    ## Slow requests

    Every request that spent a second or more in the normalizer. The chart shows whether they are spread out or arrive together: a cluster at one moment across several pods points at the backend, and a cluster on one pod points at that pod or at one client's large batches.
    """)
    return


@app.cell
def slow(LogNorm, df, mo, nodenorm_logs, plt):
    slow_table = df.loc[
        df["time_taken_ms"] >= nodenorm_logs.SLOW_REQUEST_MS,
        ["time", "time_taken_ms", "curie_count", "ms_per_curie", "options_label", "node_name", "pod", "curies_preview"],
    ].sort_values("time_taken_ms", ascending=False)
    mo.stop(slow_table.empty, mo.md(f"No request took {nodenorm_logs.SLOW_REQUEST_MS / 1000:.0f} s or more."))

    _fig, _ax = plt.subplots(figsize=(14, 4.5))
    _points = _ax.scatter(
        slow_table["time"], slow_table["time_taken_ms"] / 1000, c=slow_table["curie_count"], s=14,
        norm=LogNorm(vmin=1, vmax=max(slow_table["curie_count"].max(), 10)), cmap="viridis",
    )  # fmt: skip
    _ax.set_yscale("log")
    _ax.set_ylabel("Time taken (s)")
    _ax.set_title(
        f"The {len(slow_table):,} requests that took {nodenorm_logs.SLOW_REQUEST_MS / 1000:.0f} s or more "
        f"(the smallest was for {slow_table['curie_count'].min():,} CURIEs)"
    )
    _ax.grid(True, which="both", alpha=0.3)
    _fig.colorbar(_points, ax=_ax, label="CURIEs in request", pad=0.01)
    _fig.autofmt_xdate()
    _fig.tight_layout()

    mo.vstack(
        [
            _fig,
            mo.md("Slowest first. `curies_preview` is the start of what was asked for."),
            mo.ui.table(slow_table.round({"time_taken_ms": 0, "ms_per_curie": 2}), selection=None, page_size=15),
        ]
    )
    return


@app.cell(hide_code=True)
def repeats_header(mo):
    mo.md(r"""
    ## Repeat lookups

    How often the same CURIE is asked for again. This is what a cache in front of NodeNorm, or in a client, could save: a CURIE asked for 1,000 times needs 999 fewer lookups if its answer is kept.

    Counting every distinct CURIE takes a second pass over the logs and a lot of memory (about a minute and 8 GB for three months of dev logs, which name 21 million distinct CURIEs), so it runs only when asked. It covers everything loaded; the filters above do not apply.
    """)
    return


@app.cell
def repeats_button(mo):
    repeats_button = mo.ui.run_button(label="Count every CURIE")
    repeats_button
    return (repeats_button,)


@app.cell
def repeats_count(LOG_DIR, mo, nodenorm_logs, repeats_button):
    mo.stop(not repeats_button.value, mo.md("*Not counted in this run.*"))

    with mo.status.spinner(title="Counting every CURIE in the logs"):
        curie_counts = nodenorm_logs.count_curies(LOG_DIR)
    return (curie_counts,)


@app.cell
def repeats(curie_counts, mo, np, pd, plt):
    _counts = np.sort(np.fromiter(curie_counts.values(), dtype=np.int64, count=len(curie_counts)))[::-1]
    _total, _distinct = int(_counts.sum()), len(_counts)
    _cumulative = 100 * np.cumsum(_counts) / _total

    # How much of the traffic the N most requested CURIEs account for: the best a cache of N
    # entries could do, if it somehow knew in advance which N to keep.
    _sizes = np.unique(np.minimum(np.round(10 ** np.arange(0, np.log10(_distinct) + 0.25, 0.25)).astype(int), _distinct))
    _fig, _ax = plt.subplots(figsize=(10, 4.5))
    _ax.plot(_sizes, _cumulative[_sizes - 1], marker="o", markersize=3)
    _ax.set_xscale("log")
    _ax.set_xlabel("Number of most-requested CURIEs")
    _ax.set_ylabel("Share of all lookups (%)")
    _ax.set_ylim(0, 100)
    _ax.set_title("How much of the traffic the most requested CURIEs account for")
    _ax.grid(True, which="both", alpha=0.3)
    _fig.tight_layout()

    _by_prefix = pd.DataFrame(
        [(_c.partition(":")[0] if ":" in _c else "(no prefix)", _n) for _c, _n in curie_counts.items()],
        columns=["prefix", "lookups"],
    ).groupby("prefix")["lookups"].agg(lookups="sum", distinct="size")
    _by_prefix["lookups per distinct CURIE"] = _by_prefix["lookups"] / _by_prefix["distinct"]
    _by_prefix.insert(1, "% of lookups", 100 * _by_prefix["lookups"] / _total)
    repeats_by_prefix = _by_prefix.sort_values("lookups", ascending=False)

    mo.vstack(
        [
            mo.hstack(
                [
                    mo.stat(f"{_total:,}", label="CURIE lookups"),
                    mo.stat(f"{_distinct:,}", label="Distinct CURIEs"),
                    mo.stat(f"{1 - _distinct / _total:.0%}", label="Lookups that were repeats", caption="the most a perfect cache could save"),
                    mo.stat(f"{(_counts == 1).sum() / _distinct:.0%}", label="CURIEs asked for only once"),
                ],
                widths="equal",
            ),
            _fig,
            mo.md("The most requested CURIEs:"),
            mo.ui.table(pd.DataFrame(curie_counts.most_common(25), columns=["CURIE", "lookups"]), selection=None, pagination=False),
            mo.md("By prefix, over every CURIE in every request (not only the first):"),
            mo.ui.table(repeats_by_prefix.round(2).reset_index(), selection=None, page_size=15),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
