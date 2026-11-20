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

The notebook loads the Sterling web log archives, one `.tar.gz` per month, from
`data/log-analysis/nodenorm/pjl-upload/`:

```
data/log-analysis/nodenorm/pjl-upload/
├── node-normalization-web-logs-2025-11.tar.gz
├── node-normalization-web-logs-2025-12.tar.gz
└── node-normalization-web-logs-2026-01.tar.gz
```

These three are the months it loads by default. To analyse other months, download those archives
into the same directory and edit the `logfiles_json_tar_gz` list in the notebook's "Loading
files" section.

### CloudWatch (not loaded by the current notebook)

Logs can also be exported from AWS CloudWatch Logs Insights with this query:

```
fields @timestamp, @message, @logStream, @log
| filter @message like "normalizer:get_normalized_nodes"
| sort @timestamp desc
| limit 10000
```

(Why 10K? Because that's the maximum it'll let you download.) Download them in JSON: some lines
will still be truncated, but the JSON will be well-formed. The notebook has no loader for this
format, so using such an export means adding one.
