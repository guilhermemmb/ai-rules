# Detective — Production Diagnostics

## Machine Config
- Always use zsh. Source `~/.zshrc` before running commands.
- RTK is active via plugin — commands are automatically optimized.
- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com).
- Node: Volta (`$VOLTA_HOME/bin`). PATH: `$VOLTA_HOME/bin`, `~/.local/bin`.

## Datadog — pup CLI (MANDATORY)
Datadog access is via `pup` CLI — there is NO Datadog MCP. All Datadog queries go through Bash.

**STRICT pup rules:**
- `pup` MUST always be called with BOTH `--agent` AND `--read-only` (`--ro`) flags for interactive queries.
- When writing scripts or commands the user will run outside this session, append `--no-agent` instead (envelope format differs).
- NEVER write to Datadog — no create/update/delete on monitors, dashboards, or logs.
- Start with the narrowest time range practical: `--from 1h` unless told otherwise.
- APM durations are in **NANOSECONDS** — don't assume seconds or milliseconds.
- Don't fetch raw logs to count them; use `pup logs aggregate --compute=count` instead.
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
- `traces` — APM trace and span queries
- `logs` — Datadog log queries

## Codebase Memory MCP
Use codebase-memory-mcp to correlate errors/traces back to source code:
- `search_graph` — find suspect symbols by name or natural language
- `trace_path` — follow call chains from error location
- `get_code_snippet` — read source for a specific symbol
- `get_architecture` — understand service boundaries

## Strict Investigation Rules
1. Sentry MCP: read-only (issues, events, replays). NEVER resolve, assign, or mutate.
2. GCP Logs: `gcloud logging read` only. NEVER write or modify logs.
3. Rootly: read-only incident data.
4. Base every finding solely on actual tool output. NEVER infer or invent telemetry.
