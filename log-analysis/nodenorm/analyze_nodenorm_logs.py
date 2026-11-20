import marimo

__generated_with = "0.25.2"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # NodeNorm Log Analysis

    As of [PR #312](https://github.com/TranslatorSRI/NodeNormalization/pull/312), NodeNorm produces logs in the format:

    ```
    2025-06-18T03:26:30-04:00	2025-06-18 07:26:30,635 | INFO | normalizer:get_normalized_nodes | Normalized 1 nodes in 1.21 ms with arguments (curies=['UMLS:C0132098'], conflate_gene_protein=True, conflate_chemical_drug=True, include_descriptions=False, include_individual_types=True)
    ```

    This notebook is intended to be used in analysing these logs.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Loading files

    These files are read from `data/log-analysis/pjl-upload/` at the repository root, which is gitignored. They are far too large to check in — a single month of web logs is hundreds of megabytes — so keep them there and out of the repository.
    """)
    return


@app.cell
def _(mo):
    # Anchored on the notebook's directory rather than the cwd, which is wherever marimo was launched from.
    LOG_DIR = mo.notebook_dir().parents[1] / "data" / "log-analysis" / "pjl-upload"
    logfiles_json_tar_gz = [
        LOG_DIR / "node-normalization-web-logs-2025-11.tar.gz",
        LOG_DIR / "node-normalization-web-logs-2025-12.tar.gz",
        LOG_DIR / "node-normalization-web-logs-2026-01.tar.gz",
    ]
    return (logfiles_json_tar_gz,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    We can use Python dataclasses to load the important information from the logfile.
    """)
    return


@app.cell
def _():
    import json
    from dataclasses import dataclass
    from datetime import datetime
    import logging
    import re
    import ast
    import statistics

    return ast, dataclass, datetime, json, logging, re, statistics


@app.cell
def _(ast, dataclass, datetime, logging, re):
    logging.basicConfig(level=logging.INFO)

    @dataclass
    class LogEntry:
        time: datetime
        curies: list[str]
        curie_count: int
        time_taken_ms: float
        time_taken_per_curie_ms: float
        arguments: dict[str, str]
        node: str = ""

    def convert_log_line_into_entry(line: str) -> list[LogEntry]:
        # Depending on where the log file comes from, it might start with one of two types of timestamps:
        # - ISO 8601 date (e.g. "2007-04-05T12:30−02:00"), which will be separated from the rest of the log line with a tab character.
        # - Python log format date (e.g. "2025-06-12 13:01:49,319"), which should always be in UTC.

        # Entry variables.
        log_time = None
        curies = []
        curie_count = -1
        time_taken_ms = -1.0
        arguments = {}

        # Parse the datetime stamp.
        iso8601date_match = re.match(r'^(\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:[\.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?)?)?) |', line)
        if iso8601date_match:
            log_time = datetime.fromisoformat(iso8601date_match.group(1))
        else:
            raise ValueError(f"Could not identify the datetime for the line: '{line}'")

        # Is the log line too long?
        if len(line) > 49_151: # Longest we've seen is 114688, and that was truncated.
            return []

        # Parse the log text.
        log_text_match = re.search(r'\| INFO \| normalizer:get_normalized_nodes \| Normalized (\d+) nodes in ([\d\.]+) ms with arguments \((.*)\)', line)
        if not log_text_match:
            raise ValueError(f"Could not find NodeNorm log-line (length: {len(line)}): {line}")
        curie_count = int(log_text_match.group(1))
        time_taken_ms = float(log_text_match.group(2))
        argument_text = log_text_match.group(3)

        # To parse the argument_text, we can turn it into a function call and use Python's ast module to parse it.
        argument_fn_call = f'arguments({argument_text})'
        tree = ast.parse(argument_fn_call, mode="eval")
        call_node = tree.body
        for kw in call_node.keywords:
            arguments[kw.arg] = ast.literal_eval(kw.value)

        # Some assertions.
        if 'curies' not in arguments:
            raise ValueError(f'No CURIEs found in arguments {argument_text} on line {line}, which was parsed into: {arguments}')
        curies = arguments['curies']
        if len(curies) != curie_count:
            raise ValueError(f'Found {len(curies)} CURIEs in arguments but expected {curie_count} CURIEs: {curies}')
        if len(curies) < 1:
            raise ValueError(f'Found no CURIEs in line: {line}')

        # Emit the LogEntry.
        return [LogEntry(
            time=log_time,
            curies=curies,
            curie_count=curie_count,
            time_taken_ms=time_taken_ms,
            time_taken_per_curie_ms=time_taken_ms/curie_count,
            arguments=arguments
        )]

    return (convert_log_line_into_entry,)


@app.cell
def _(convert_log_line_into_entry, json, logfiles_json_tar_gz):
    import tarfile

    logs = []
    _count_skipped = 0
    for _logfile in logfiles_json_tar_gz:
        _logline_count = 0
        with tarfile.open(_logfile, "r|gz") as _tar:
            print(f"Loading logfile {_logfile}")

            for _member in _tar:
                if _member.isfile():
                    if not _member.name.lower().endswith(".json"):
                        print(f"Skipping member {_member}")
                        continue

                    # The entire log file from AWS is one massive JSON list *curses*.
                    _datas = json.load(_tar.extractfile(_member))

                    for _data in _datas:
                        if len(_data) > 2:
                            raise ValueError(f"Invalid data: expected query and results, but got: {json.dumps(_data)}")

                        # _data[0] is the query; _data[1] holds its results.
                        for _result in _data[1]['data']['result']:
                            # Each JSON file from the Sterling logs consists of multiple entries.
                            # Each entry has a values field, which is a list of rows.
                            # Each row is a list with two items: a timestamp and a log line.
                            for [_, _line] in _result['values']:
                                # We're only interested in log-lines -- these will all contain `normalizer:get_normalized_nodes`
                                if "normalizer:get_normalized_nodes" not in _line:
                                    print(f"SKIPPING line '{_line}' because it isn't one of interest.")
                                    _count_skipped += 1
                                    continue

                                logs.extend(convert_log_line_into_entry(_line))
                                _logline_count += 1
        print(f"Loaded {_logline_count:,} lines from {_logfile}")

    print(f"Loaded {len(logs):,} log entries in total, skipped {_count_skipped} lines.")
    return (logs,)


@app.cell
def _(logs):
    logs[:10]
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Some overall measures
    """)
    return


@app.cell
def _(logs):
    times = sorted(list(set(map(lambda x: x.time, logs))))
    count_requests = len(logs)
    unique_curies = sorted(set([x for xs in map(lambda x: x.curies, logs) for x in xs]))
    return count_requests, times, unique_curies


@app.cell
def _(count_requests, logs, statistics, times, unique_curies):
    time_taken_ms = list(map(lambda x: x.time_taken_ms, logs))
    time_taken_per_curie_ms = list(map(lambda x: x.time_taken_per_curie_ms, logs))
    curie_count = list(map(lambda x: x.curie_count, logs))

    print(f"Time range: {times[0]} to {times[-1]} ({times[-1] - times[0]})")
    print(f"Total number of requests: {count_requests:,}")
    print(f"Total number of CURIEs: {sum(curie_count):,}")
    print(f"Minimum number of CURIEs: {min(curie_count):,}")
    print(f"Mean number of CURIEs: {sum(curie_count)/count_requests}")
    print(f"Median number of CURIEs: {statistics.median(curie_count)}")
    print(f"Modal number of CURIEs: {statistics.mode(curie_count)}")
    print(f"Maximum number of CURIEs: {max(curie_count):,}")
    print(f"Total time taken: {sum(map(lambda x: x.time_taken_ms, logs)):,} ms")
    print(f"Minimum time per request: {min(time_taken_ms)} ms")
    print(f"Average time per request: {sum(time_taken_ms)/count_requests} ms")
    print(f"Maximum time per request: {max(time_taken_ms)} ms")
    print(f"Minimum time per CURIE: {min(time_taken_per_curie_ms)} ms")
    print(f"Average time per CURIE: {sum(time_taken_per_curie_ms)/count_requests} ms")
    print(f"Maximum time per CURIE: {max(time_taken_per_curie_ms)} ms")
    print(f"Total number of unique CURIEs: {len(unique_curies):,}")
    return


@app.cell
def _(logs):
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    from dataclasses import asdict

    df = pd.DataFrame([asdict(r) for r in logs])
    df['curie_count'] = df['curie_count'].astype(int)
    df['time'] = pd.to_datetime(df['time'])
    df['throughput_cps'] = df['curie_count'] / df['time_taken_ms'] * 1000
    print(f"Throughput: {df['throughput_cps'].mean()} (min: {df['throughput_cps'].min()}, max: {df['throughput_cps'].max()}) CURIES per second")
    return df, plt, sns


@app.cell
def _(df, plt, sns):
    sns.histplot(df['time_taken_ms'], bins=20, kde=False, binrange=(0, 10)) #100))
    plt.title("Time taken per request (ms)")
    plt.tight_layout()
    plt.gca()
    return


@app.cell
def _(df, plt, sns):
    sns.histplot(df['time_taken_per_curie_ms'], bins=20, kde=False, binrange=(0, 10)) #100))
    plt.title("Time taken per CURIE (ms)")
    plt.tight_layout()
    plt.gca()
    return


@app.cell
def _(df, plt, sns):
    # Plot requests against time.
    _requests_per_day = df.set_index('time').resample('D').size()
    sns.barplot(x=_requests_per_day.index, y=_requests_per_day.values)
    plt.title("Requests per day")
    plt.xlabel("Day")
    plt.ylabel("Number of Requests")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.gca()
    return


@app.cell
def _(df, plt, sns):
    # Plot the frequency distribution of requests grouped by hour.
    _requests_per_hour = df.set_index('time').resample('h').size()
    sns.histplot(_requests_per_hour, bins=10, stat='percent')
    plt.title("Requests per Hour")
    plt.xlabel("Number of requests")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.gca()
    return


@app.cell
def _(df, plt, sns):
    # Plot the frequency distribution of CURIE counts grouped by hour.
    # TODO: fix this graph
    _curies_per_hour = df.set_index('time').resample('h')['curie_count'].sum()
    sns.histplot(_curies_per_hour, stat='percent')
    plt.title('CURIEs per Hour')
    plt.xlabel('Number of CURIEs')
    plt.ylabel('Frequency')
    plt.tight_layout()
    plt.gca()
    return


@app.cell
def _(df, plt, sns):
    # Plot CURIEs over time (by hour)
    # Fix this graph
    _curies_per_hour = df.set_index('time').resample('h')['curie_count'].sum()
    sns.lineplot(x=_curies_per_hour.index, y=_curies_per_hour.values)
    plt.title('CURIEs per Hour')
    plt.xlabel('Time')
    plt.ylabel('Number of CURIEs')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.gca()
    return


@app.cell
def _(df, plt, sns):
    # Plot CURIEs against hour of day
    sns.barplot(x=df['time'].dt.hour, y=df['curie_count'])
    plt.title("CURIEs per Hour")
    plt.xlabel("Hour (UTC)")
    plt.ylabel("Number of CURIEs")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.gca()
    return


@app.cell
def _(df, plt, sns):
    # CURIEs per request
    sns.histplot(df['curie_count'], bins=50, stat='percent')
    plt.title(f"CURIEs per request (max = {max(df['curie_count'])})")
    plt.xlabel("Number of CURIEs")
    plt.ylabel("Frequency")
    plt.gca()
    return


@app.cell
def _(df, plt, sns):
    # CURIEs per request (but only from 1-10)
    sns.histplot(df['curie_count'], bins=10, binrange=(1, 10), stat='percent')
    plt.title("CURIEs per request (from 1-10)")
    plt.xlabel("Number of CURIEs")
    plt.ylabel("Frequency")
    plt.gca()
    return


@app.cell
def _(df, plt, sns):
    # Time taken distribution
    sns.histplot(df['time_taken_ms'], bins=20, stat="percent")
    plt.title("Time taken")
    plt.xlabel("Time taken (ms)")
    plt.ylabel("Frequency")
    plt.gca()
    return


@app.cell
def _(df, plt, sns):
    # Time per CURIE distribution
    sns.histplot(df['time_taken_per_curie_ms'], bins=30, stat="percent")
    plt.title("Time taken per CURIE")
    plt.xlabel("Time taken per CURIE (ms)")
    plt.ylabel("Frequency")
    plt.gca()
    return


if __name__ == "__main__":
    app.run()
