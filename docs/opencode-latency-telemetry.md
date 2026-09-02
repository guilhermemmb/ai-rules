# OpenCode latency telemetry

`scripts/opencode-latency-report.py` is an installation-free, local reporter
for latency experiments. It reads an OpenCode SQLite database in SQLite
read-only URI mode and emits metadata only. It does not proxy model traffic,
change orchestration, or send telemetry anywhere.

## Usage

No package installation is required:

```zsh
python3 scripts/opencode-latency-report.py
python3 scripts/opencode-latency-report.py --db /path/to/opencode.db --since 24h
python3 scripts/opencode-latency-report.py --db /path/to/opencode.db --session SESSION_ID --json
```

`--since` accepts positive compact durations such as `30m`, `24h`, `7d`, or
`1h30m`. Human-readable output is intended for quick inspection. `--json` is
stable machine-readable output with `schema_version`, `sessions`, `aggregate`,
`unknowns`, and `warnings` fields. The current report schema is
`schema_version: 1`. A reader that encounters a `schema_version` other than
`1` must not assume the report shape: treat the report as unknown and re-derive
the fields from the source OpenCode schema rather than interpreting the payload
against version 1.

### Finding the database

Use `--db` when possible. Without it, the reporter checks the conventional
locations in this order:

1. `$XDG_DATA_HOME/opencode/opencode.db` (or `~/.local/share/opencode/opencode.db`)
2. `~/Library/Application Support/opencode/opencode.db`
3. `~/Library/Application Support/Opencode/opencode.db`
4. `~/.config/opencode/opencode.db`

OpenCode versions and operating systems can use different locations. The
reporter does not create, migrate, lock for writing, or repair a database. A
missing or incompatible schema produces warnings and partial output rather
than stopping orchestration.

### Part association

The reporter supports OpenCode schemas where a part links directly through
`session_id`, and schemas where a part has only `message_id`. For the latter,
it resolves the message through the allow-listed message identifier and uses
that message's session association. If the message table is unavailable, the
message identifier is unsafe, or the association cannot be resolved, that row
is skipped with a warning; the rest of the report remains available. This
also applies to tool/MCP counts, part token counters, and assistant-output
timing recovered through message-linked parts.

## Privacy and operational behavior

- Only standard-library Python modules are used.
- The database connection is opened with `file:...?...mode=ro` and `uri=True`.
- The parser allow-lists session/message/part identifiers, timestamps,
  agent/model/provider IDs, roles/types, tool names, retry/fallback flags, and
  token counters.
- Prompt text, source code, raw tool arguments, raw tool output, credentials,
  API keys, and arbitrary `part.data` fields are not emitted. Unknown JSON
  fields are discarded after metadata extraction. Malformed JSON is reported
  only as a table/row warning, without including the payload or parser text.
- Only `session_id` or a safely resolved `message_id` association is used for
  part rows. Missing linkage, unsupported columns, and unresolved associations
  produce explicit warnings and partial output rather than silent loss.
- Identifiers are bounded before output. The report includes the database
  filename, not the full local path.
- There is no proxy, LiteLLM, Helicone integration, network call, or remote
  telemetry by default. Phoenix/OTLP is deliberately documented as a future
  sink until a stable, explicitly configured local endpoint and export
  contract are available.
- The reporter is an offline post-run tool. It cannot block orchestration;
  callers should run it after a run or against a copy of the database.

## What is measured

For each selected session the report attempts to provide start/end timestamps,
wall duration, agents, models and providers, input/output/cache-read/cache-write
tokens, tool and MCP counts/durations, retry/fallback indicators, and overlap
metadata. Model duration and TTFT are marked `*_approx`: they are inferred from
timestamps available in the local schema, not measured at the provider socket.
Unknown fields are listed explicitly, and schema/JSON problems appear in
`warnings` while the rest of the report remains usable.

The aggregate includes p50 and p95 for wall duration and the approximate model
duration/TTFT values that were available. Percentiles are calculated only over
the selected sessions with a known value; missing values are not treated as
zero.

## Measurement procedure

Use repeatable prompts and record the exact model profile, reasoning setting,
repository state, machine state, and selected session IDs alongside each run.
Keep the reporter outside the timed operation.

### Cold versus warm p50/p95

1. Pick a fixed task and fixed model/reasoning configuration.
2. Cold batch: restart the relevant process or clear the intended application
   cache according to the experiment protocol, then run at least 10 isolated
   sessions. Do not mix setup time into the task unless it is the thing being
   measured.
3. Warm batch: run the same task at least 10 times without clearing the cache.
4. Export each batch with `--json --session` or `--since`, save the JSON, and
   compare `aggregate.latency_ms.wall.p50` and `.p95`. Also compare token and
   approximate TTFT fields.
5. Report the batch size, discarded/unknown sessions, overlap/concurrency, and
   any warnings. A p95 from fewer than 10 observations is a directional signal,
   not a stable service benchmark.

### Direct versus orchestrated

Run equivalent cold and warm batches in two conditions: a direct OpenCode
agent invocation and the same task through the orchestrator. Keep the task,
repository, profile, approval behavior, and concurrency policy constant. Use
the session-level wall/TTFT values for end-to-end comparison; use tool/MCP
counts and overlap fields to explain orchestration overhead. Do not claim the
model duration approximation is a provider latency measurement.

### Reasoning-tier sweep

For each chosen reasoning tier, run an equal-size batch with the same prompt,
model, context, and warm/cold state. Label the tier outside the report (for
example, low/medium/high), then compare wall p50/p95, approximate TTFT,
output tokens, tool count, and unknown rates. Change one tier at a time and
avoid pooling tiers into one percentile distribution.

### Reviewer sweep 1/2/3

Run the same implementation/review workload with reviewer sweep 1, 2, and 3 as
separate batches. Keep the review scope and diff fixed. Record whether each
sweep is parallel or sequential, because overlapping windows can change wall
time. Compare p50/p95, retry/fallback indicators, tool/MCP duration, and total
tokens per sweep. The reporter observes what the database records; it does not
infer reviewer correctness or quality.

### Cache-token validation

Validate cache behavior independently of latency:

1. Run a cold session and save its JSON report.
2. Repeat the identical task warm, without changing the model or context.
3. Confirm that `tokens.cache_read` and/or `tokens.cache_write` are populated
   when the OpenCode/provider schema records them.
4. Compare input, output, cache-read, and cache-write counters with provider
   billing/usage metadata when available. A zero or unknown counter is not
   proof that caching is disabled: the local schema or provider may not expose
   it.
5. Repeat after a deliberate context change to ensure a cache hit is not being
   assumed from latency alone.

## Limitations

- OpenCode's SQLite schema can change. Table and column discovery is dynamic,
  but fields that are absent are reported as unknown.
- The reporter is best-effort for schemas with `session`, `message`, and
  `part`/`data` records. Parts can be session-linked or message-linked, but it
  cannot recover metadata that is not stored locally or safely associate a
  part whose message is absent.
- TTFT and model durations are timestamp approximations. They include local
  persistence/scheduling effects and do not provide provider-side queue,
  network, first-byte, or token-stream timings.
- Session overlap is inferred from complete session windows. Tool overlap is
  inferred from complete tool windows and may reflect persistence granularity.
- Retry/fallback detection is limited to explicit metadata and recognizable
  status values. Multiple observed models alone are not called a fallback.
- A copied database is the safest manual inspection input. SQLite read-only
  mode prevents writes, but it does not conceal data from the process that is
  explicitly given the database path.
- Phoenix/OTLP export is not implemented. Adding an export endpoint without a
  stable local contract could leak metadata or introduce a blocking dependency,
  so a future task must provide explicit opt-in configuration and non-fatal
  failure handling before adding it.
