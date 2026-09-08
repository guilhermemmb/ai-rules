# Reference

Compact registries for the `ai-rules` repository. Each entry links to its
authoritative source definition rather than reproducing it. This registry covers
only files tracked in the repository; it does not pretend to enumerate installed
or generated files under `~/.config/opencode/` or `~/.agents/` that are not in
this repo.

> **Labels:** `Current` = present in tracked source; `Proposed` = recommended,
> not implemented; `installed (not tracked)` = referenced by repo config but
> defined outside the repo.

---

## 1. Rules

All under [`.rulesync/rules/`](../.rulesync/rules/). Root rules are distributed
as global prompt overrides.

| Rule | Purpose | Path |
| :--- | :--- | :--- |
| overview | Global instructions: branch naming, git safety, forbidden commands, PR routing | [`overview.md`](../.rulesync/rules/overview.md) |
| custom-rules | T-shirt sizing, SDD, review routing, parallel specialist decomposition, commits, packages, delegation | [`custom-rules.md`](../.rulesync/rules/custom-rules.md) |
| code-exploration | RTK/native discovery routing | [`code-exploration.md`](../.rulesync/rules/code-exploration.md) |
| git-safety | Git/GitHub safety (no push, commit approval, PR generate-only, API read-only) | [`git-safety.md`](../.rulesync/rules/git-safety.md) |
| pr-workflow | PR creation/update format and command format | [`pr-workflow.md`](../.rulesync/rules/pr-workflow.md) |
| security-scan | On-demand commit/push safety checklist | [`security-scan.md`](../.rulesync/rules/security-scan.md) |
| context7 | Library/API documentation lookup protocol | [`context7.md`](../.rulesync/rules/context7.md) |
| figma-code-connect | Code Connect `.figma.ts` template authoring | [`figma-code-connect.md`](../.rulesync/rules/figma-code-connect.md) |
| figma-design-to-code | Figma design → code workflow | [`figma-design-to-code.md`](../.rulesync/rules/figma-design-to-code.md) |
| figma-mcp-server | Figma MCP server reference and tool catalog | [`figma-mcp-server.md`](../.rulesync/rules/figma-mcp-server.md) |

---

## 2. Skills

All under [`.rulesync/skills/`](../.rulesync/skills/), grouped by purpose.

### Orchestration & planning

| Skill | Purpose | Path |
| :--- | :--- | :--- |
| brainstorming | L/XL Phase 1: intent, approaches, spec | [`brainstorming/SKILL.md`](../.rulesync/skills/brainstorming/SKILL.md) |
| writing-plans | L/XL Phase 2: implementation plan | [`writing-plans/SKILL.md`](../.rulesync/skills/writing-plans/SKILL.md) |
| executing-plans | L/XL Phase 3: per-task dispatch + review | [`executing-plans/SKILL.md`](../.rulesync/skills/executing-plans/SKILL.md) |
| reviewing-plans | L/XL Phase 4: final comprehensive review (opt-in) | [`reviewing-plans/SKILL.md`](../.rulesync/skills/reviewing-plans/SKILL.md) |
| verification-planning | Verification/evidence planning | [`verification-planning/SKILL.md`](../.rulesync/skills/verification-planning/SKILL.md) |
| deepwork | High-cost multi-phase coordination | [`deepwork/SKILL.md`](../.rulesync/skills/deepwork/SKILL.md) |
| orca-orchestration | Multi-agent coordination via Orca | [`orca-orchestration/SKILL.md`](../.rulesync/skills/orca-orchestration/SKILL.md) |
| reflect | Review past sessions for reusable patterns | [`reflect/SKILL.md`](../.rulesync/skills/reflect/SKILL.md) |
| project-context | Summarize project context and constraints | [`project-context/SKILL.md`](../.rulesync/skills/project-context/SKILL.md) |

### Review & quality

| Skill | Purpose | Path |
| :--- | :--- | :--- |
| review-pipeline | On-demand orchestrator-managed policy, packet, lane, phase, and verdict contract | [`review-pipeline/SKILL.md`](../.rulesync/skills/review-pipeline/SKILL.md) + [`pipeline.json`](../.rulesync/skills/review-pipeline/pipeline.json) |
| simplify | Clarity/readability without behavior change | [`simplify/SKILL.md`](../.rulesync/skills/simplify/SKILL.md) |

### Implementation specialist

| Skill | Purpose | Path |
| :--- | :--- | :--- |
| fixer | Bounded implementation specialist workflow | [`fixer/SKILL.md`](../.rulesync/skills/fixer/SKILL.md) |

### Discovery & codebase

| Skill | Purpose | Path |
| :--- | :--- | :--- |
| clonedeps | Clone dependency source for inspection | [`clonedeps/SKILL.md`](../.rulesync/skills/clonedeps/SKILL.md) |
| codemap | Generate hierarchical codemaps | [`codemap/SKILL.md`](../.rulesync/skills/codemap/SKILL.md) |
| cortex | Gorgias domain knowledge via Context Layer MCP | [`cortex/SKILL.md`](../.rulesync/skills/cortex/SKILL.md) |
| oh-my-opencode-slim | Tune OMO agents/prompts/config | [`oh-my-opencode-slim/SKILL.md`](../.rulesync/skills/oh-my-opencode-slim/SKILL.md) |

### Datadog observability

Detective's read-only skill subset is `dd-pup`, `dd-apm`, `dd-logs`, `dd-symdb`,
`traces`, and `logs`; the remaining skills here are mutation-oriented and are
not assigned to Detective.

| Skill | Purpose | Path |
| :--- | :--- | :--- |
| dd-pup | Datadog CLI (`pup`) auth/ops | [`dd-pup/SKILL.md`](../.rulesync/skills/dd-pup/SKILL.md) |
| dd-apm | Traces, services, dependencies | [`dd-apm/SKILL.md`](../.rulesync/skills/dd-apm/SKILL.md) |
| dd-logs | Log management, search, pipelines | [`dd-logs/SKILL.md`](../.rulesync/skills/dd-logs/SKILL.md) |
| dd-monitors | Monitor management and alerting | [`dd-monitors/SKILL.md`](../.rulesync/skills/dd-monitors/SKILL.md) |
| dd-debugger | Live debugger / log probes | [`dd-debugger/SKILL.md`](../.rulesync/skills/dd-debugger/SKILL.md) |
| dd-symdb | Symbol database / probe-able methods | [`dd-symdb/SKILL.md`](../.rulesync/skills/dd-symdb/SKILL.md) |
| dd-triage-flaky-test | Flaky-test triage | [`dd-triage-flaky-test/SKILL.md`](../.rulesync/skills/dd-triage-flaky-test/SKILL.md) |
| dd-unblock-pr | Failing PR CI triage | [`dd-unblock-pr/SKILL.md`](../.rulesync/skills/dd-unblock-pr/SKILL.md) |
| traces | APM traces and spans | [`traces/SKILL.md`](../.rulesync/skills/traces/SKILL.md) |
| logs | Datadog log search/analysis | [`logs/SKILL.md`](../.rulesync/skills/logs/SKILL.md) |
| incident-response | On-call/incident coordination | [`incident-response/SKILL.md`](../.rulesync/skills/incident-response/SKILL.md) |

### Browser

| Skill | Purpose | Path |
| :--- | :--- | :--- |
| agent-browser | Browser automation CLI | [`agent-browser/SKILL.md`](../.rulesync/skills/agent-browser/SKILL.md) |

### Figma

| Skill | Purpose | Path |
| :--- | :--- | :--- |
| figma-design-to-code | Design → code | [`figma-design-to-code/SKILL.md`](../.rulesync/skills/figma-design-to-code/SKILL.md) |
| figma-code-connect | `.figma.ts` Code Connect templates | [`figma-code-connect/SKILL.md`](../.rulesync/skills/figma-code-connect/SKILL.md) |
| figma-use | Figma Plugin API write/read | [`figma-use/SKILL.md`](../.rulesync/skills/figma-use/SKILL.md) |
| figma-implement-motion | Motion/animation → code | [`figma-implement-motion/SKILL.md`](../.rulesync/skills/figma-implement-motion/SKILL.md) |
| figma-generate-library | Design system generation | [`figma-generate-library/SKILL.md`](../.rulesync/skills/figma-generate-library/SKILL.md) |

### Screenshot

| Skill | Purpose | Path |
| :--- | :--- | :--- |
| screenshot | Beautiful code/terminal/snippet screenshots | [`screenshot/SKILL.md`](../.rulesync/skills/screenshot/SKILL.md) |

### Referenced but not tracked

The OMO orchestrator preset in
[`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) also references
`orca-cli`, which has **no tracked** `.rulesync/skills/` directory in this
repository. It is `installed (not tracked)` — defined outside the repo (e.g.
under `~/.agents/skills/` / `~/.claude/skills/`).

---

## 3. Custom subagents

### Built-in (7 — OMO Slim presets)

Defined in [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) under
`presets.bifrost`.

| Agent | Default model | Role |
| :--- | :--- | :--- |
| Orchestrator | `bf-o/gpt-5.6-luna` | Master delegator & coordinator |
| Oracle | `bf-o/gpt-5.6-terra` | Strategic advisor, architecture |
| Explorer | DeepSeek V4 Flash | Codebase reconnaissance |
| Librarian | `bf-o/gpt-5.6-luna` | Knowledge retrieval |
| Designer | `bf/huggingface/together/zai-org/GLM-5.2` | UI/UX |
| Fixer | `bf-o/gpt-5.6-luna` | Implementation |
| Observer | Gemini 3 Flash | Visual analysis |

### Custom agents

| Agent | Definition source | Model (default) | Role |
| :--- | :--- | :--- | :--- |
| Navigator | [`.rulesync/subagents/navigator.md`](../.rulesync/subagents/navigator.md) | Gemini 3 Flash | Browser automation via `agent-browser` CLI |
| Detective | [`.rulesync/subagents/detective.md`](../.rulesync/subagents/detective.md) | `bf-o/gpt-5.6-luna` | Production diagnostics via `pup`/`gcloud` (read-only) |
| Sage | [`.rulesync/subagents/sage.md`](../.rulesync/subagents/sage.md) | `bf-o/gpt-5.6-terra` | Gorgias domain knowledge via Cortex |
| reviewer-code … reviewer-simplifier (10 lanes) | [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json) + [`pipeline.json`](../.rulesync/skills/review-pipeline/pipeline.json) | Mixed: Luna/Terra/Flash/Gemini | Read-only review specialist lanes directly managed by the orchestrator |

The ten reviewer lanes are: `reviewer-code`, `reviewer-test`,
`reviewer-errors`, `reviewer-types`, `reviewer-security`,
`reviewer-performance`, `reviewer-data-integrity`, `reviewer-accessibility`,
`reviewer-comments`, `reviewer-simplifier`. Lane identity, order, triggers,
phase, policy, packet, and verdict definitions are canonical in
`.rulesync/skills/review-pipeline/pipeline.json`; model prompts and permissions
remain in `oh-my-opencode-slim.json` (not in `.rulesync/subagents/`).

The first nine lanes run in Phase A batches; `reviewer-simplifier` runs exactly
once sequentially in Phase B when executable/source/config content applies.
The orchestrator loads the skill on demand, selects and directly dispatches
lanes, reconciles exact sessions, aggregates findings, computes the verdict,
and renders the report. Do not infer a second registry from this summary.

Per-agent appended prompt instructions live in
[`.rulesync/oh-my-opencode-slim/`](../.rulesync/oh-my-opencode-slim/)
(`{agent}_append.md`).

---

## 4. Scripts

All under [`scripts/`](../scripts/).

| Script | Purpose |
| :--- | :--- |
| `validate-ai-rules.py` | Repository validator (static validation of rules/config) |
| `update-agents-overview-data.py` | Regenerate `agents-overview/data.yaml` |
| `opencode-latency-report.py` | OpenCode latency telemetry reporting |
| `review_pipeline_contract.py` | Deterministic review packet, lane-result, and verdict contract helpers |
| `test_review_pipeline_contract.py` | Deterministic contract tests for the canonical review registry and health-first verdicts |

Deployment logic itself is [`deploy.sh`](../deploy.sh) at the repo root.

---

## 5. Models and providers

Model routing lives directly in [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json),
which is the sole model configuration. Built-in agents resolve from the active
`bifrost` preset and custom agents are declared under `agents.*`, with their
model and variant values kept together. The provider catalog remains in
[`opencode.json`](../opencode.json) (`bf`, `bf-a`, `bf-o`) and only defines
available providers/models. The review-pipeline `model_profile_key` remains a
stable lane identifier and is not a deploy profile.

---

## 6. MCPs

Repository MCP definitions: [`.rulesync/mcp.jsonc`](../.rulesync/mcp.jsonc).
Agent assignments: [`oh-my-opencode-slim.json`](../oh-my-opencode-slim.json).

| MCP | Enabled (source) | Assigned to (source) |
| :--- | :--- | :--- |
| context7 | ✓ | Librarian |
| github | ✓ | Orchestrator |
| sentry | ✗ | — (Detective reports it unavailable) |
| linear | ✓ | Librarian |
| gcp-logging | ✗ | Detective uses `gcloud` CLI instead |
| cortex | ✓ | Sage, Librarian |
| notion | ✗ | — |
| rootly | ✗ | — (Detective reports it unavailable) |
| gorgias-mcp | ✗ | — |
| figma-mcp | ✓ | Designer |

> `sentry`, `notion`, and `rootly` are declared `enabled: false` in
> [`.rulesync/mcp.jsonc`](../.rulesync/mcp.jsonc). The Detective agent definition
> reports those sources as unavailable rather than attempting to call them; see
> [`review-and-improvements.md`](./review-and-improvements.md) (F1, resolved).

Datadog and GCP Logs are accessed via `pup` and `gcloud` CLIs (Bash), not MCP.
`pup` must always be called with `--agent --read-only`.

### Code intelligence lifecycle

RTK/native OpenCode tools are authoritative for exact local work, review inputs,
and source confirmation. Serena is the active semantic MCP for OpenCode IDE
sessions and complements those exact-tool workflows. GitNexus is removed and is
not an authority or part of deployment or review.

Serena is declared canonically in [`.rulesync/mcp.jsonc`](../.rulesync/mcp.jsonc)
and uses only OpenCode's `ide` context over stdio. Its dashboard and browser are
disabled, and VS Code integration is deferred. The parent worktree's complete,
generated, read-only configuration is [`.serena/project.yml`](../.serena/project.yml);
all other `.serena` runtime files are ignored. Install the pinned version with:

```zsh
uv tool install -p 3.13 serena-agent==1.7.0
```

Worktrunk creates or enters the worktree, but does not own Serena's lifecycle:
it does not start, index, stop, or clean Serena. OpenCode starts Serena with
`--context ide --project-from-cwd`; Serena resolves the nearest
`.serena/project.yml` or `.git` boundary, and each client session owns one
stdio process. Launching from nested `ai-rules` selects its nested Git boundary
and does not inherit the parent `.serena/project.yml`; nested configuration is
deferred because Worktrunk worktrees need no changes inside it.

---

## 7. Key output paths

| Path | Purpose |
| :--- | :--- |
| `~/.config/opencode/opencode.json` | Installed provider + MCP + plugin config (generated) |
| `~/.config/opencode/oh-my-opencode-slim.json` | Installed per-agent model/variant/skills/MCP (generated) |
| `~/.config/opencode/.ai-rules.manifest.json` | Deployment owner/manifest/SHA-256 (generated) |
| `~/.config/opencode/oh-my-opencode-slim/{agent}_append.md` | Per-agent prompt overrides (generated) |
| `~/.config/opencode/AGENTS.md` | OMO-managed global instructions (generated) |
| `~/.cache/opencode/agent-output/navigator/` | Navigator write target |
| `~/.cache/opencode/agent-output/sage/` | Sage write target |
| `/tmp/pr-<branch>.md` | PR description (ephemeral) |
| `~/developer/planning-docs/{{repository-name}}/.planning/specs/` | SDD design docs |
| `~/developer/planning-docs/{{repository-name}}/.planning/plans/` | SDD implementation plans |
| `~/developer/planning-docs/{{repository-name}}/.planning/ledger-<plan>.md` | Execution ledger |
| `~/developer/planning-docs/{{repository-name}}/.planning/reports/` | Per-task implementer reports |

Generated files under `~/.config/opencode/` are owned by `deploy.sh` and must
not be edited directly.

---

## 8. Interactive visualization

[`agents-overview/`](../agents-overview/README.md) (`data.yaml` + `index.html`)
is the interactive agent-pantheon visualization and is complementary to this
registry; it is not regenerated by the documentation atlas.
