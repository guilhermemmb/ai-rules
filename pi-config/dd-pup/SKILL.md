---
name: dd-pup
description: Datadog CLI (pup). OAuth2 auth with token refresh.
metadata:
  version: "1.0.0"
  author: datadog-labs
  repository: https://github.com/datadog-labs/agent-skills
  tags: datadog,cli,dd-pup,pup
  alwaysApply: "false"
---

# pup (Datadog CLI)

Pup CLI for Datadog API operations. Supports OAuth2 and API key auth.

## Installation

Install Pup with Homebrew:

```bash
brew tap datadog-labs/pack
brew install pup
```

Verify the installation:

```bash
pup --version
```

## Authentication

OAuth2 is the recommended authentication method:

```bash
pup auth login
pup auth status
pup auth refresh
pup auth logout
```

Tokens expire after approximately one hour. If a command returns 401 or 403,
try `pup auth refresh` first, then run `pup auth login` if refresh fails.

For headless or CI use, configure the required environment variables:

```bash
export DD_API_KEY=your-api-key
export DD_APP_KEY=your-app-key
export DD_SITE=datadoghq.com
```

## CLI Safety and Discovery

Pup returns JSON by default. Use `pup --help` and `pup <command> --help` to
inspect the installed CLI rather than relying on stale command examples.

For production investigations, call Pup with `--agent --ro` and keep the first
query to the narrowest practical range, usually `--from 1h`. Do not mutate
Datadog resources from a read-only diagnostic workflow.

This skill is the CLI and authentication foundation only. Use the focused skills
for operation-specific guidance:

- `dd-logs` — log search, pipelines, archives, and cost control
- `dd-apm` — APM services, traces, dependencies, and performance analysis
- `dd-monitors` — monitor management and alerting
- `dd-debugger` — live debugger probes
- `dd-symdb` — probe-able method discovery

Incident commands are intentionally not duplicated here; use `pup incidents
--help` and `pup on-call --help` for the installed CLI surface.

## Common Auth Errors

| Error | Cause | Fix |
| --- | --- | --- |
| 401 Unauthorized | Token expired | `pup auth refresh` |
| 403 Forbidden | Missing scope | Check app-key permissions |
| 404 Not Found | Wrong resource ID | Verify the resource exists |
| Rate limited | Too many requests | Narrow the query and retry later |

## Sites

| Site | `DD_SITE` value |
| --- | --- |
| US1 (default) | `datadoghq.com` |
| US3 | `us3.datadoghq.com` |
| US5 | `us5.datadoghq.com` |
| EU1 | `datadoghq.eu` |
| AP1 | `ap1.datadoghq.com` |
| US1-FED | `ddog-gov.com` |
