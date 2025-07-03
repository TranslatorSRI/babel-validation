# Logs

To download logs from AWS, using the following Logs Insights query:

```
fields @timestamp, @message, @logStream, @log
| filter @message like "normalizer:get_normalized_nodes"
| sort @timestamp desc
| limit 10000
```

(Why 10K? Because that's the maximum it'll let you download.)

Download the logs in JSON. Some of them will still be truncated, but
at least the JSON will be well-formed.
