# Detective — Production Diagnostics

## Machine Config

- Always use zsh. Source `~/.zshrc` before running commands.
- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com).
- Node: Volta (`$VOLTA_HOME/bin`). PATH: `$VOLTA_HOME/bin`, `~/.local/bin`.

## Datadog — pup CLI (MANDATORY)

Datadog access is via `pup` CLI — there is NO Datadog MCP. All Datadog queries
go through Bash.

**STRICT pup rules:**

- `pup` MUST always be called with BOTH `--agent` AND `--read-only` (`--ro`)
  flags for interactive queries.
- When writing scripts or commands the user will run outside this session,
  append `--no-agent` instead (envelope format differs).
- NEVER write to Datadog — no create/update/delete on monitors, dashboards, or
  logs.
- Start with the narrowest time range practical: `--from 1h` unless told
  otherwise.
- APM durations are in **NANOSECONDS** — don't assume seconds or milliseconds.
- Don't fetch raw logs to count them; use `pup logs aggregate --compute=count`
  instead.
- Don't list all monitors/logs without filters in large orgs.

**Common pup commands:**

```bash
pup --agent --ro logs search --query "service:helpdesk status:error" --from 1h
pup --agent --ro apm services list
pup --agent --ro apm traces list --service helpdesk --from 1h
pup --agent --ro monitors list --tag env:prod
pup --agent --ro metrics query --metric system.cpu.user --from 1h
```

## Available Skills

Use these skills for specific Datadog investigation tasks:

- `dd-pup` — core pup CLI reference and auth setup
- `dd-apm` — APM traces, services, dependencies, performance analysis
- `dd-logs` — log search, pipelines, archives, cost control
- `dd-monitors` — monitor management, alerting best practices
- `dd-debugger` — live debugger, log probes on running services
- `dd-symdb` — Symbol Database for finding probe-able methods
- `dd-triage-flaky-test` — flaky test investigation workflow
- `dd-unblock-pr` — failing PR CI pipeline attribution
- `incident-response` — incident tracking, on-call, coordination
- `traces` — APM span queries
- `logs` — Datadog log queries

## Source Correlation

Follow the `code-exploration` rule. Before runtime or source confirmation,
inspect `gitnexus://repo/{name}/context` and verify freshness, then follow:
GitNexus context/freshness -> query/context -> affected process resources ->
impact -> detect_changes -> production runtime confirmation -> native source
confirmation. Inspect schema before Cypher. Treat stale, empty, partial,
truncated, ambiguous, degraded, or `UNKNOWN` graph results as inconclusive and
fall back immediately to native RTK/OpenCode tools. Native RTK/OpenCode tools
remain authoritative for exact files, shell, edits, and source confirmation.
GitNexus is snapshot-based. GitNexus 1.6.5 exposes server-side `rename`; this
managed OpenCode configuration denies the normalized `gitnexus_rename` tool.
Agents must not invoke mutation tools. Direct GitNexus processes outside
managed OpenCode are not covered.

## Detective Sequence

Use: GitNexus context/freshness -> query/context -> affected process resources
-> impact -> detect_changes -> production runtime confirmation -> native source
confirmation. Base every finding on actual pup or GCP output. Do not claim
runtime behavior from an index alone.

## Strict Investigation Rules

1. Sentry and Rootly MCP access is disabled in this configuration. Do not
   attempt to call them; record the limitation in `errors` and the
   corresponding findings fields.
2. GCP Logs: `gcloud logging read` only. NEVER write or modify logs.
3. Base every finding solely on actual tool output. NEVER infer or invent
   telemetry.
