# Review and Improvement Proposals

> **Status:** Documentation only. This page records a static source/configuration
> review and a documentation audit. It proposes remediation but changes nothing:
> no runtime configuration, agent prompts, permissions, model profiles,
> deployment code, scripts, MCP configuration, or generated outputs are modified
> by this document. Proposals are **future work**, not implemented changes.
>
> **Review baseline:** refreshed **as of 2026-09-02** against the current tree
> (OpenCode-only hardening). Each finding below carries a resolution status, and
> findings are split into **resolved/historical** versus **open** in
> [Resolution status](#resolution-status). Where a finding is marked resolved,
> the recorded evidence reflects the state *before* the change; the status line
> records the verified current state.

This document is the canonical human-readable record of the review performed as
part of the documentation atlas. It complements [`architecture.md`](architecture.md),
which describes the same system's layers and authority boundaries, and
[`reference.md`](reference.md), which provides compact registries. Where the two
disagree in emphasis, this document is the one that carries severity, impact,
and remediation ordering.

- [Scope and method](#scope-and-method)
- [Labels](#labels)
- [Resolution status](#resolution-status)
- [Findings](#findings)
- [Speed/maintenance vs safety/correctness](#speedmaintenance-vs-safetycorrectness)
- [Prioritized roadmap](#prioritized-roadmap)
- [Decision table](#decision-table)

## Scope and method

This review is **static**: it reads tracked source and generated artifacts in the
repository and correlates them with the review evidence already recorded in
[`README.md`](../README.md) and [`docs/architecture.md`](architecture.md). It is
**not** a runtime verification pass.

- **In scope:** source/configuration consistency, documentation accuracy,
  authority/precedence ambiguity, and the test/validation posture of the
  repository's own tooling.
- **Out of scope:** live runtime behavior, effective permissions inside a running
  OpenCode process, actual MCP reachability, and whether Claude Code is correctly
  deployed on this machine. Those require runtime probes (the `smoke-*` scripts)
  and are only *proposed* here.
- **Stop condition applied:** any claim that cannot be supported by tracked source
  or supplied review evidence is labeled **Unverified**, not stated as fact.

## Labels

Reused from [`architecture.md`](architecture.md#label-legend) with one addition:

- **Current** — present, source-recorded behavior.
- **Validated** — confirmed by the cross-artifact validator or a recorded
  smoke/check run.
- **Observed** — seen in an installed artifact or runtime probe.
- **Proposed** — a recommendation for future work; **not** implemented.
- **Unverified** — not provable from this static pass; recorded without asserting
  a runtime conclusion.

## Resolution status

Refreshed against the current tree (2026-09-02). Resolved findings are kept for
history; open findings remain proposals.

| Finding | Status | Note |
| :--- | :--- | :--- |
| F1 MCP availability | **Resolved** | `sentry`, `notion`, `rootly` set `"enabled": false` in `.rulesync/mcp.jsonc`; detective prose agrees. |
| F2 Competing agent authorities | **Partially resolved** | Detective `tools`/`mcps`/permissions reconciled; broader single-authority model + validator drift check remains open. |
| F3 Detective isolation | **Resolved** | Mutation-capable skills removed from detective (frontmatter + OMO); read-only diagnostics retained. |
| F4 Claude Code alignment | **Resolved (obsolete)** | `claudecode` target removed; repository is OpenCode-only. |
| F5 Model-profile authority | **Resolved** | Profiles are schema version 1 with per-agent `model` + optional `variant`; applier validates and applies both. |
| F6 Two-config precedence | **Open** | `opencode.json` top-level model vs OMO per-agent precedence still unrecorded. |
| F7 Lint autofix wording | **Resolved** | Converged to check-only-by-default across `custom-rules.md`, `orchestrator_append.md`, `fixer_append.md`. |
| F8 `clonedeps`/Git wording | **Resolved** | `clonedeps` now applies the confirmation rule to clone/fetch/`ls-remote`. |
| F9 Validator/smoke test coverage | **Narrowed** | `test_model_profile.py` and `test_deploy_compatibility.py` added; validator/smoke scripts still lack direct coverage. |
| F10 Compatibility preflight | **Resolved** | Normal deploy skips compatibility probing; `--compatibility-check` remains the explicit gate. |
| F11 Skill provenance | **Partially resolved** | `skills-lock.json` now covers all 34 tracked skills; validator lock coverage still not enforced. |

## Findings

Eleven findings, ordered by risk: five **high**, five **medium**, one **low**.
Each finding lists severity, evidence (paths and line ranges), impact, and the
simplest proposed remediation.

### F1. Contradictory MCP availability — **High** → **Resolved**

**Status:** Resolved. `sentry`, `notion`, and `rootly` are now
`"enabled": false` in [`.rulesync/mcp.jsonc`](../.rulesync/mcp.jsonc), matching
the detective narrative.

**Evidence**

- [`.rulesync/mcp.jsonc:25-29`](../.rulesync/mcp.jsonc) declares `sentry`
  `"enabled": true`.
- [`.rulesync/mcp.jsonc:50-54`](../.rulesync/mcp.jsonc) declares `rootly`
  `"enabled": true`.
- [`.rulesync/subagents/detective.md:28-30`](../.rulesync/subagents/detective.md)
  and [`:36-37`](../.rulesync/subagents/detective.md): "Sentry and Rootly MCP
  access is disabled in this configuration."
- [`.rulesync/oh-my-opencode-slim/detective_append.md:61-62`](../.rulesync/oh-my-opencode-slim/detective_append.md):
  "Sentry and Rootly MCP access is disabled."
- [`README.md:451`](../README.md): `sentry ❌ disabled`; [`README.md:455`](../README.md):
  `rootly ❌ disabled`.
- [`oh-my-opencode-slim.json:141`](../oh-my-opencode-slim.json) (detective prompt):
  "Sentry and Rootly MCP access is disabled in this configuration."

**Impact** — The source declares `sentry` and `rootly` enabled, but the agent
prompt, the appended rules, and the README all claim they are disabled. An
operator (or agent) cannot tell whether these servers are actually registered;
the contradiction weakens trust in the MCP inventory and could cause an agent to
attempt a call the operator believes is off.

**Proposed remediation** — Align the `enabled` flags in `.rulesync/mcp.jsonc`
with the detective narrative (set `sentry`/`rootly` to `"enabled": false`, or add
an explicit comment explaining the intended state), then reconcile the README
inventory with that single source.

### F2. Competing custom-agent authorities — **High** → **Partially resolved**

**Status:** Partially resolved. The concrete detective `tools`/`mcps`/permission
discrepancy cited below is fixed (detective frontmatter is now `tools: [read, bash]`,
`mcps: []`, matching OMO's deny-write permission block). The broader single
authority-per-agent model and validator drift check remain open.

**Evidence**

- [`.rulesync/subagents/`](../.rulesync/subagents/) defines `detective`,
  `navigator`, `sage` with YAML frontmatter (`model`, `tools`, `mcps`, `skills`).
- [`oh-my-opencode-slim.json:71-724`](../oh-my-opencode-slim.json) `agents.*`
  re-defines the same three agents plus `reviewer` and ten `reviewer-*` lanes
  with `model`, `variant`, `mcps`, `skills`, `permission`, `prompt`,
  `orchestratorPrompt`.
- [`oh-my-opencode-slim.json:133-134`](../oh-my-opencode-slim.json) sets
  detective `edit: deny`, `write: deny`, while
  [`.rulesync/subagents/detective.md:5`](../.rulesync/subagents/detective.md)
  declares `tools: [read, write, bash]`.
- The ten `reviewer-*` lanes exist **only** in `oh-my-opencode-slim.json`
  (lines 263-724); they have no `.rulesync/subagents/*.md` definition.

**Impact** — The same agent is described in multiple, overlapping sources with no
recorded precedence rule. The effective tool set and prompt depend on which
source wins at install time, and the discrepancy is concretely visible
(`write` in one source, denied in the other). This is the core authority risk the
review surfaced.

**Proposed remediation** — Establish one authoritative source per agent
(suggested: `oh-my-opencode-slim.json` for runtime model/variant/permissions,
`.rulesync/subagents/*.md` for prompt prose), and extend the validator to fail on
cross-source disagreement (tool/permission drift).

### F3. Mutation-capable skills on the read-only Detective — **High** → **Resolved**

**Status:** Resolved. Detective's skill list is now read-only diagnostics only
(`dd-pup`, `dd-apm`, `dd-logs`, `dd-symdb`, `traces`, `logs`) in both the
frontmatter and OMO config; mutation-oriented skills were removed.

**Evidence**

- [`oh-my-opencode-slim.json:105-117`](../oh-my-opencode-slim.json) and
  [`.rulesync/subagents/detective.md:7-20`](../.rulesync/subagents/detective.md)
  assign detective the skills `dd-monitors`, `dd-debugger`, `dd-triage-flaky-test`,
  `dd-unblock-pr`, `incident-response`.
- [`.rulesync/skills/dd-monitors/SKILL.md`](../.rulesync/skills/dd-monitors/SKILL.md)
  — "Monitor management - create, update, mute".
- [`.rulesync/skills/dd-debugger/SKILL.md`](../.rulesync/skills/dd-debugger/SKILL.md)
  — "placing log probes on methods".
- [`.rulesync/skills/dd-triage-flaky-test/SKILL.md`](../.rulesync/skills/dd-triage-flaky-test/SKILL.md)
  — recommends "quarantine".
- Detective is otherwise read-only:
  [`oh-my-opencode-slim.json:118-140`](../oh-my-opencode-slim.json) denies
  `write`/`edit`/`apply_patch` and restricts `bash` to `pup --agent --ro *` and
  `gcloud logging read *`.

**Impact** — The detective's prompt and permissions say "never mutate", but its
skill list includes skills whose whole purpose is mutation (create/mute monitors,
place live-debugger probes, quarantine tests). A skill load is not a permission
grant, but the contradiction invites a mutation attempt the permission layer must
then deny — a correctness/safety smell on the agent whose job is read-only
diagnostics.

**Proposed remediation** — Remove the mutation-capable skills from detective (keep
`dd-pup`, `dd-apm`, `dd-logs`, `dd-symdb`, `traces`, `logs`), and gate any future
mutation behind a separate, approval-gated agent.

### F4. Unaligned Claude Code deployment — **High** → **Resolved (obsolete)**

**Status:** Resolved. `claudecode` was removed from [`rulesync.jsonc`](../rulesync.jsonc)
targets; the repository is now OpenCode-only.

**Evidence**

- [`rulesync.jsonc:2`](../rulesync.jsonc) declares `"targets": ["claudecode", "opencode"]`.
- [`.rulesync/rules/custom-rules.md:56-58`](../.rulesync/rules/custom-rules.md)
  references "Claude Code: Preserve the existing `@reviewer` compatibility
  coordinator".
- [`deploy.sh`](../deploy.sh) stages only `rulesync generate --targets opencode`
  (see [`docs/architecture.md`](architecture.md#rulesync-vs-omo-vs-native-opencode-vs-claude-code));
  no Claude Code deployment path is exercised by the recorded deploy script.
- [`README.md:414-423`](../README.md) "Configuration Layers" lists only
  OpenCode/OMO paths; there is no Claude Code layer.

**Impact** — The rules declare Claude Code a target and a review coordinator, but
the repository's deploy and validation tooling only covers OpenCode. The Claude
Code alignment is asserted in prose, never produced or verified by the tooling.
This is **Unverified** at runtime.

**Proposed remediation** — Either add a Claude Code deployment/validation path to
`deploy.sh`/the validator, or explicitly descope Claude Code from this repository
and remove the `claudecode` target so the source no longer claims unmanaged
alignment.

### F5. Partially controlled model profiles — **High** → **Resolved**

**Status:** Resolved. Profiles are schema version 1 with per-agent `model` plus
optional `variant`; [`apply-model-profile.py`](../scripts/apply-model-profile.py)
validates and applies both, and focused profile tests were added.

**Evidence**

- [`profiles/models/default.yml`](../profiles/models/default.yml) and
  [`profiles/models/cost-efficient.yml`](../profiles/models/cost-efficient.yml)
  contain model IDs only (no variants, skills, MCPs, or permissions).
- [`README.md:121-126`](../README.md): "model profiles contain model IDs only;
  reasoning variants are defined by OMO agent configuration and are not stored in
  the YAML profiles."
- [`scripts/apply-model-profile.py:26-44`](../scripts/apply-model-profile.py)
  patches only the `model` field; `variant`, `skills`, `mcps`, `permission` are
  left untouched.
- [`oh-my-opencode-slim.json:10,38,50,62,103,201`](../oh-my-opencode-slim.json)
  carries `variant` (`high`/`medium`/`low`) outside the profiles.

**Impact** — `--model-profile=<name>` only swaps model IDs. The reasoning variant,
skills, MCP assignment, and permissions remain governed by OMO config that is not
validated against the active profile, so "profile" and "effective model routing"
can drift apart. **Unverified** which combination actually takes effect.

**Proposed remediation** — Make profiles authoritative for every model attribute
(including `variant`), have `apply-model-profile.py` write all of them, and add a
validator check that the active profile matches the installed OMO config.

### F6. Two-config OpenCode precedence — **Medium** → **Open**

**Status:** Open. Precedence between top-level `opencode.json` model and OMO
per-agent model remains unrecorded.

**Evidence**

- [`opencode.json:78-79`](../opencode.json) sets top-level `model` and
  `small_model`; [`opencode.json:640`](../opencode.json) sets `enabled_providers`.
- [`oh-my-opencode-slim.json:6-69`](../oh-my-opencode-slim.json) `presets.bifrost`
  sets per-agent `model`/`variant`/`skills`/`mcps`.
- [`README.md:414-423`](../README.md) lists both files but states no precedence.

**Impact** — The same model concepts are declared in two files; the effective
precedence between the top-level native config and the OMO preset is unrecorded.
See [`docs/architecture.md`](architecture.md#two-plus-one-opencode-config-files)
for the related `opencode.jsonc` generated file. **Ambiguous/Unverified**.

**Proposed remediation** — Document (or eliminate) the precedence: make one file
the single authority for model selection and state it explicitly in the README
Configuration Layers table.

### F7. Contradictory lint autofix guidance — **Medium** → **Resolved**

**Status:** Resolved. The three sources now converge on "check-only by default;
autofix only on an explicit `Lint Autofix` directive" ([`.rulesync/rules/custom-rules.md`](../.rulesync/rules/custom-rules.md),
[`.rulesync/oh-my-opencode-slim/orchestrator_append.md`](../.rulesync/oh-my-opencode-slim/orchestrator_append.md),
[`.rulesync/oh-my-opencode-slim/fixer_append.md`](../.rulesync/oh-my-opencode-slim/fixer_append.md)).

**Evidence**

- [`.rulesync/rules/custom-rules.md:157`](../.rulesync/rules/custom-rules.md):
  "Always run lint to fix files before finishing an implementation."
- [`.rulesync/oh-my-opencode-slim/orchestrator_append.md:60`](../.rulesync/oh-my-opencode-slim/orchestrator_append.md):
  "Always run lint to fix files before finishing an implementation."
- [`.rulesync/oh-my-opencode-slim/fixer_append.md:26-27`](../.rulesync/oh-my-opencode-slim/fixer_append.md):
  "Always run lint validation (check-only, no autofix) before finishing an
  implementation. Only run lint with autofix when the handoff explicitly includes
  a `Lint Autofix` directive."

**Impact** — The global rule (and the orchestrator append) instructs autofix,
while the fixer append — the instruction that actually reaches the implementing
agent — instructs check-only by default. The two directives are contradictory and
can produce either an unwanted autofix or a missed one depending on which rule is
loaded.

**Proposed remediation** — Converge on "check-only by default; autofix only on an
explicit `Lint Autofix` directive" across `custom-rules.md`,
`orchestrator_append.md`, and `fixer_append.md`.

### F8. `clonedeps` vs Git confirmation conflict — **Medium** → **Resolved**

**Status:** Resolved. [`clonedeps/SKILL.md`](../.rulesync/skills/clonedeps/SKILL.md)
now applies the repository confirmation rule to every git command, including
`git clone`, `git fetch`, and `git ls-remote`.

**Evidence**

- [`.rulesync/skills/clonedeps/SKILL.md:153-165`](../.rulesync/skills/clonedeps/SKILL.md):
  "Clone/fetch with normal git commands" (uses `git ls-remote`, `git clone`).
- [`.rulesync/skills/clonedeps/SKILL.md:100-101`](../.rulesync/skills/clonedeps/SKILL.md):
  "Ask for confirmation before network cloning unless the user explicitly asked
  to clone immediately."
- [`.rulesync/oh-my-opencode-slim/orchestrator_append.md:54`](../.rulesync/oh-my-opencode-slim/orchestrator_append.md):
  "Never run any git command on your own — always ask and confirm first. Covers
  commit, push, checkout, rebase, merge."
- [`.rulesync/rules/git-safety.md:16-23`](../.rulesync/rules/git-safety.md):
  commit requires explicit confirmation.

**Impact** — The global rule opens with an absolute "never run any git command
without confirmation", while `clonedeps` permits cloning once the user has asked
for clones "immediately". It is ambiguous whether `git clone`/`git ls-remote` sit
inside the confirmation gate, creating a possible path around a safety rule.

**Proposed remediation** — Enumerate exactly which git commands the global rule
gates (commit, push, checkout, rebase, merge) and explicitly state that `clonedeps`
clone/fetch is a separate, user-confirmed workflow, so the two rules cannot be
read as contradictory.

### F9. Brittle, lightly tested validator/smoke scripts — **Medium** → **Narrowed**

**Status:** Narrowed. Test coverage has grown beyond the single latency-reporter
test, but the validator and smoke scripts themselves still lack direct coverage.

**Evidence**

- [`scripts/validate-ai-rules.py`](../scripts/validate-ai-rules.py) — 3,215 lines
  with ~51 top-level methods; it is the primary static safety evidence.
- [`scripts/smoke-opencode-fixer-runtime.sh`](../scripts/smoke-opencode-fixer-runtime.sh) —
  502 lines.
- [`scripts/smoke-opencode-reviewer-runtime.sh`](../scripts/smoke-opencode-reviewer-runtime.sh) —
  1,043 lines.
- Three test files now exist:
  [`scripts/test_opencode_latency_report.py`](../scripts/test_opencode_latency_report.py)
  (tests `opencode-latency-report.py`),
  [`scripts/test_model_profile.py`](../scripts/test_model_profile.py)
  (profile schema/applier tests), and
  [`scripts/test_deploy_compatibility.py`](../scripts/test_deploy_compatibility.py)
  (deployment/preflight tests). None of the three covers the validator or the
  smoke scripts directly.

**Impact** — Profile application and deployment preflight now have focused
coverage, but the validator and the smoke scripts — the repository's safety and
runtime-evidence backbone — still have no direct test coverage. A regression
there silently weakens every future deployment's assurance.

**Proposed remediation** — Add focused unit tests for the validator's checks and
the smoke scripts' parsing/reporting logic, and extract shared helpers so the
scripts are testable and maintainable.

### F10. Expensive compatibility preflight — **Medium** → **Resolved**

**Status:** Resolved. Normal deployment no longer probes host/package
compatibility; the explicit, fail-closed gate is `--compatibility-check`.

**Evidence**

- [`deploy.sh`](../deploy.sh) `preflight_compatibility` (currently around line
  1005) spawns `opencode --version` and reads the OMO, `@opencode-ai/plugin`,
  and `@opencode-ai/sdk` package metadata plus an optional evidence file.
- [`deploy.sh`](../deploy.sh) `run_compatibility_check` (around line 1587) is the
  only fail-closed caller that blocks when `COMPATIBILITY_STATUS` is not
  `matched`.
- [`deploy.sh`](../deploy.sh) `run_deploy` (around line 1654) intentionally does
  **not** call `preflight_compatibility`; the comment at that site records that
  normal deployment skips host/package probing.
- [`README.md`](../README.md) documents the preflight and the
  `--compatibility-check` gate.

**Impact** — Every deploy/check pays a host-version spawn plus three package-metadata
reads for what is only read-only diagnostics. It is heavier than the cheap static
checks and blocks the opt-in smoke path on an unknown/skewed status.

**Proposed remediation** — Split the preflight: keep the cheap static checks on the
normal deploy path and run the expensive version probing only under
`--compatibility-check`/`--force`, or cache the package-metadata reads.

### F11. Incomplete skill provenance — **Low** → **Partially resolved**

**Status:** Partially resolved. `skills-lock.json` now records every tracked
skill (34 entries) with source/version where known and explicit `provenance:
unknown` otherwise; validator enforcement of lock coverage is still not
implemented.

**Evidence**

- [`skills-lock.json`](../skills-lock.json) now locks all **34** tracked skills.
  `agent-browser` (source `vercel-labs/agent-browser`) and the eight `dd-*`
  skills (source `datadog-labs/agent-skills`, with `version`) carry recorded
  provenance; the remaining skills are marked `provenance: unknown` with a local
  hash.
- [`.rulesync/skills/`](../.rulesync/skills/) contains 34 vendored skills; only
  **9** carry recorded provenance (the eight `dd-*` skills via `metadata.repository`
  plus `agent-browser` from the lockfile).

**Impact** — The origin and version of ~32 of 33 vendored skills are untracked,
which makes auditing, upgrading, and reproducing the skill set harder.

**Proposed remediation** — Extend `skills-lock.json` (or the per-skill frontmatter)
to record source and version for every vendored skill, and have the validator
enforce lock coverage.

## Speed/maintenance vs safety/correctness

Remediations split into two tracks so a reader can act on low-risk simplifications
without implying they resolve the authority risks.

| Track | Findings | Nature |
| :--- | :--- | :--- |
| **Safety / correctness** | F1 (MCP availability), F2 (agent authorities), F3 (Detective isolation), F4 (Claude alignment), F5 (profile authority), F6 (config precedence) | Authority and capability boundaries; changing these alters agent behavior or permissions and needs care + approval. |
| **Speed / maintenance** | F7 (lint autofix wording), F8 (clonedeps/Git wording), F9 (validator/test consolidation), F10 (preflight splitting), F11 (provenance/locking) | Wording reconciliation, test/tooling hygiene, and performance; lower risk, mostly mechanical or additive. |

## Prioritized roadmap

Ordered by dependency and risk. Items are marked **done** where the finding is now
resolved in tracked source; the rest remain **Proposed**.

1. **Authority model** (F2, F6, F1) — **partial**: F1 done (MCP flags
   reconciled), F2 partial (detective reconciled; validator drift check open),
   F6 open. Establish one recorded precedence model and make the validator fail
   on cross-source drift.
2. **Detective capability isolation** (F3) — **done**: mutation-capable skills
   removed; detective `tools`/`mcps`/permissions reconciled.
3. **Claude Code alignment** (F4) — **done**: `claudecode` descoped; repository is
   OpenCode-only.
4. **Profile authority** (F5) — **done**: profiles are schema version 1 with
   per-agent `model` + optional `variant`; applier validates and applies both.
5. **Validator/test consolidation** (F9) — **partial**: profile and deploy-preflight
   tests added; validator and smoke scripts still lack direct coverage.
6. **Provenance & duplication reduction** (F11, F7, F8, F10) — **mostly done**:
   F7/F8/F10 resolved; F11 partial (lockfile expanded, validator coverage still
   open).

## Decision table

For each proposal: is it documentation-only, does it need runtime validation,
does it need user approval, or is it out of scope for this documentation pass?

| Proposal | Track | Docs-only? | Needs runtime validation? | Needs user approval? | Out of scope here? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Reconcile MCP `enabled` flags (F1) | Safety | No — edits `.rulesync/mcp.jsonc` | No | **Yes** (changes live MCP registration) | Yes |
| Single agent-authority model + validator drift check (F2, F6) | Safety | No | **Yes** (effective tools/permissions are runtime) | **Yes** | Yes |
| Detective skill isolation (F3) | Safety | No | **Yes** (confirm no mutation path) | **Yes** | Yes |
| Claude Code alignment or descope (F4) | Safety | No | **Yes** (if deployed) | **Yes** | Yes |
| Profile authority + variant validation (F5) | Safety | No | **Yes** (effective model check) | **Yes** | Yes |
| Lint autofix wording (F7) | Speed | **Yes** (docs/rules text only) | No | No | Yes |
| `clonedeps`/Git wording (F8) | Speed | **Yes** (docs/rules text only) | No | No | Yes |
| Validator/smoke test consolidation (F9) | Speed | No — adds tests | No | No | Yes |
| Split compatibility preflight (F10) | Speed | No — edits `deploy.sh` | No | No | Yes |
| Extend skill provenance/locking (F11) | Speed | Partially (metadata) | No | No | Yes |
| Produce this review document | — | **Yes** (this file) | No | No | **No — this pass** |

> All proposal rows are out of scope for *this documentation pass* by design; the
> only in-scope deliverable is this review document and the report it is produced
> from. The "Docs-only?" column records whether the *future* change is itself
> limited to documentation, to help sequence follow-up work. As of 2026-09-02,
> rows marked Resolved in [Resolution status](#resolution-status) have since been
> implemented in tracked source; the remaining rows are still open proposals.
