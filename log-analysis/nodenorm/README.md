# NodeNorm log analysis

`analyze_nodenorm_logs.py` is a [marimo](https://marimo.io/) notebook that analyses NodeNorm's
request logs. Open it from the repository root with:

```bash
uv run marimo edit log-analysis/nodenorm/analyze_nodenorm_logs.py
```

It reads the logs from
`data/log-analysis/nodenorm/` at the repository root (`../../data/log-analysis/nodenorm/` from this
directory; other services' logs sit beside it, as `data/log-analysis/nameres/`),
which is gitignored: a single month of web logs is hundreds of megabytes, so they are kept out
of the repository rather than checked in.

## Getting the logs

Put log exports anywhere under `data/log-analysis/nodenorm/` and re-run the notebook. It reads
everything it finds there, subdirectories included, and its first table lists every file with
what was read from it, the period it covers and anything skipped. Nothing in the notebook
names a file.

What is there now is the Sterling web log archives, one `.tar.gz` per month:

```
data/log-analysis/nodenorm/pjl-upload/
├── node-normalization-web-logs-2025-11.tar.gz
├── node-normalization-web-logs-2025-12.tar.gz
└── node-normalization-web-logs-2026-01.tar.gz
```

The reading is done by `src/babel_validation/tools/nodenorm_logs.py`, which understands:

- **Loki exports** (`loki_query_results_*.json`), loose or inside a `.tar`, `.tar.gz` or
  `.tgz`. Each holds the queries that were run and their results, so the notebook knows
  which hours were downloaded, and which pod and Kubernetes node served each request.

Everything else is listed in the table as skipped, with the reason. That includes the `.csv`
twin the Sterling exports write beside each `.json` (same rows, without the query window),
plain-text pod logs, and CloudWatch exports. To read another format, add a branch to
`_read_member()` in that module.

A log entry that turns up twice, in one file or in two, is counted once, so overlapping
exports are safe to drop in together.

## Getting the numbers out

The notebook has a **Write the CSV** button that writes one row per request (time, number of
CURIEs, time taken, options, pod, node, source file) to
`exports/nodenorm-requests-<first day>-to-<last day>.generated.csv.gz` in this directory, for
anyone who wants to re-analyse the requests without parsing the log exports again. `exports/`
is gitignored: the file names pods and nodes, so share it the way you would share the logs.

### CloudWatch (no reader yet)

Logs can also be exported from AWS CloudWatch Logs Insights with this query:

```
fields @timestamp, @message, @logStream, @log
| filter @message like "normalizer:get_normalized_nodes"
| sort @timestamp desc
| limit 10000
```

(Why 10K? Because that's the maximum it'll let you download.) Download them in JSON: some lines
will still be truncated, but the JSON will be well-formed. There is no reader for this format
yet, so such an export is listed as skipped.
