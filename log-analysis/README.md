# NodeNorm log analysis

`NodeNorm_log_analysis.ipynb` analyses NodeNorm's request logs. It reads them from
`../data/log-analysis/`, which is gitignored: log dumps run from tens of megabytes to
hundreds, so they are kept out of the repository rather than checked in.

## Getting the logs

**From AWS CloudWatch Logs Insights**, using this query:

```
fields @timestamp, @message, @logStream, @log
| filter @message like "normalizer:get_normalized_nodes"
| sort @timestamp desc
| limit 10000
```

(Why 10K? Because that's the maximum it'll let you download.)

Download the logs in JSON. Some of them will still be truncated, but at least the JSON
will be well-formed. Save the file into `data/log-analysis/`.

**From the Sterling web log archives**, which the notebook loads by default: the
`node-normalization-web-logs-<year>-<month>.tar.gz` files go into
`data/log-analysis/pjl-upload/`.
