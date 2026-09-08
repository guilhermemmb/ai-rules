---
name: dd-logs
description: Log management - search, pipelines, archives, and cost control.
metadata:
  version: "1.0.0"
  author: datadog-labs
  repository: https://github.com/datadog-labs/agent-skills
  tags: datadog,logs,logging,search,dd-logs
  globs: "**/datadog*.yaml,**/*log*"
  alwaysApply: "false"
---

# Datadog Logs

Search, process, and archive logs with cost awareness.

## Prerequisites

Datadog Pup (dd-pup/pup) should already be installed:

```bash
brew tap datadog-labs/pack
brew install pup
```

## Quick Start

```bash
pup auth login
```

## Search Logs

```bash
# Basic search
pup logs search --query="status:error" --from="1h"

# With filters
pup logs search --query="service:api status:error" --from="1h" --limit 100

# JSON output is the default
pup logs search --query="@http.status_code:>=500" --from="1h"
```

Use relative ranges such as `1h`, `30m`, or `2d`; add `--to="now"` when an
explicit end time is useful. Unix timestamps and ISO timestamps are also
accepted. Start with the narrowest practical range and add `--limit` for large
result sets.

### Search Syntax

| Query                      | Meaning          |
| -------------------------- | ---------------- |
| `error`                    | Full-text search |
| `status:error`             | Tag equals       |
| `@http.status_code:500`    | Attribute equals |
| `@http.status_code:>=400`  | Numeric range    |
| `service:api AND env:prod` | Boolean          |
| `@message:*timeout*`       | Wildcard         |

Useful filters include `env:production`, `host:server-01`,
`@error.type:TimeoutError`, and escaped resource names such as
`resource:GET\ /api/users`. Combine clauses with `AND`, `OR`, and `NOT`.

## Pipelines

Process logs before indexing:

```bash
# List pipelines
pup obs-pipelines list

# Create pipeline (JSON)
pup obs-pipelines create --file pipeline.json
```

### Common Processors

```json
{
  "name": "API Logs",
  "filter": { "query": "service:api" },
  "processors": [
    {
      "type": "grok-parser",
      "name": "Parse nginx",
      "source": "message",
      "grok": {
        "match_rules": "%{IPORHOST:client_ip} %{DATA:method} %{DATA:path} %{NUMBER:status}"
      }
    },
    {
      "type": "status-remapper",
      "name": "Set severity",
      "sources": ["level", "severity"]
    },
    {
      "type": "attribute-remapper",
      "name": "Remap user_id",
      "sources": ["user_id"],
      "target": "usr.id"
    }
  ]
}
```

## ⚠️ Exclusion Filters (Cost Control)

**Index only what matters:**

```json
{
  "name": "Drop debug logs",
  "filter": { "query": "status:debug" },
  "is_enabled": true
}
```

### High-Volume Exclusions

```bash
# Find noisiest log sources
pup logs aggregate --query="*" --compute="count" --group-by="service" --from="1h"
```

| Exclude       | Query                                       |
| ------------- | ------------------------------------------- |
| Health checks | `@http.url:"/health" OR @http.url:"/ready"` |
| Debug logs    | `status:debug`                              |
| Static assets | `@http.url:*.css OR @http.url:*.js`         |
| Heartbeats    | `@message:*heartbeat*`                      |

## Archives

Store logs cheaply for compliance:

```bash
# List archives
pup logs archives list

# Archive config (S3 example)
{
  "name": "compliance-archive",
  "query": "*",
  "destination": {
    "type": "s3",
    "bucket": "my-logs-archive",
    "path": "/datadog"
  },
  "rehydration_tags": ["team:platform"]
}
```

## Log-Based Metrics

Inspect log-based metrics:

```bash
# List existing log-based metrics
pup logs metrics list
```

**⚠️ Cardinality warning:** Group by bounded values only.

## Sensitive Data

### Scrubbing Rules

```json
{
  "type": "hash-remapper",
  "name": "Hash emails",
  "sources": ["email", "@user.email"]
}
```

### Sensitive Data Handling

Avoid emitting credentials, payment data, or unnecessary personal data. Prefer
Datadog scrubbing and remappers at ingestion, and be cautious when displaying
raw log payloads.

## Read-Only Investigation Guidance

For production investigations, use `pup --agent --ro` and aggregate before
fetching large result sets:

```bash
pup --agent --ro logs search --query="service:api status:error" --from 1h
pup --agent --ro logs aggregate --query="service:api" --compute=count --from 1h
```

Present search results with timestamp, status, service, and message. If a query
returns no results, verify the service, environment, time range, and index
filters before broadening it. For invalid syntax or rate limits, report the
error and narrow or delay the next request rather than retrying blindly.

## Troubleshooting

| Problem            | Fix                            |
| ------------------ | ------------------------------ |
| Logs not appearing | Check agent, pipeline filters  |
| High costs         | Add exclusion filters          |
| Search slow        | Narrow time range, use indexes |
| Missing attributes | Check grok parser              |

## References/Documentation

- [Log Search Syntax](https://docs.datadoghq.com/logs/explorer/search_syntax/)
- [Pipelines](https://docs.datadoghq.com/logs/log_configuration/pipelines/)
- [Exclusion Filters](https://docs.datadoghq.com/logs/indexes/#exclusion-filters)
- [Archives](https://docs.datadoghq.com/logs/archives/)
