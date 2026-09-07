---
name: custom-rules
description: AI rules/agent definition for custom-rules.md
root: true
---

# Custom Rules (always applied)

## Machine Configuration

- Always use zsh. Before running any command, source my `~/.zshrc` first so the
  environment matches my interactive terminal.

## T-Shirt Sizing Workflow

Before choosing a workflow, evaluate the request and show the user the scale
`T-shirt size: XS | S | M | L | XL`, then report one selection with a short
rationale.

- **XS** — one obvious, isolated, reversible edit. State XS and immediately
  dispatch implementation to `@fixer` for code or `@designer` for UI/UX as
  appropriate; no approval, planning artifact, SDD, or reviewer.
- **S** — small local work using established patterns and straightforward
  validation.
- **M** — one cohesive bounded outcome across a small set of related files, with
  no architecture, security, migration, data-integrity, or
  external-integration uncertainty.

  S and M produce one concise merged SDD + implementation plan in
  `~/developer/planning-docs/{{repository-name}}/.planning/plans/`, containing rationale, scope/files, concrete steps,
  and validation. Present it once and wait for one approval, then dispatch
  implementation to `@fixer` for code or `@designer` for UI/UX as appropriate,
  followed automatically by one post-implementation review gate through the
  orchestrator-managed `review-pipeline` skill. Do not create
  a separate spec, load `executing-plans`, create a ledger, run a per-task
  review loop, or ask for a review choice.
- **L** — a multi-area or cross-system change, or material uncertainty.
- **XL** — architecture, migration, security/data-integrity, production-impact,
  or major external-dependency work.

  L and XL start full SDD: show a separate design/spec and ask for approval
  before writing the implementation plan. After plan approval, retain the
  `executing-plans` execution/review flow.

Subagents follow the assigned T-shirt workflow and must not bypass its approval
or artifact requirements.

## Review routing

- **OpenCode:** At review boundaries, the orchestrator loads the on-demand
  `review-pipeline` skill and is the sole review manager. It validates the
  complete packet, selects and directly dispatches the exact ten `reviewer-*`
  lanes from `.rulesync/skills/review-pipeline/pipeline.json`, runs bounded
  Phase A and conditional sequential Phase B, reconciles exact sessions,
  aggregates findings, computes the health-first verdict, and owns the final
  report. The full protocol stays out of the always-loaded orchestrator append;
  no intermediary review agent exists. Coordination or coverage failures are
  reported as Degraded/inconclusive rather than bypassed.

## Parallel Specialist Decomposition

Before implementing any non-trivial work, the Orchestrator must inspect the
plan for independent concepts, files, packages, or phases that can be executed
concurrently. This section governs bounded plan-task dispatch only; it does not
authorize arbitrary conversational tool-call parallelism. When meaningful
independent boundaries exist, split the work into the smallest complete pieces
and dispatch multiple fresh specialist lanes in the same turn:

- Use `@fixer` for independent code or mechanical implementation lanes.
- Use `@designer` for independent visual, responsive, motion, hierarchy, or
  component-feel lanes.
- Assign each lane explicit, non-overlapping file ownership, interfaces,
  acceptance criteria, validation commands, and stop conditions.
- Include the complete handoff contract for every lane: `Goal`, `Files`,
  `Steps`, `Interfaces/Constraints`, `Validation`, and `Stop Conditions`.
- OpenCode may dispatch at most **3** independent `@fixer` children in one
  implementation batch, each with `background=true`; this cap does not change
  the separate reviewer concurrency cap.
- Classify dependencies conservatively from the plan's declared `Files` and
  `Interfaces/Constraints` before dispatch:
  - Treat every path a lane may create, modify, delete, or generate as its
    write set. Overlapping write sets serialize; missing or unclear `Files`
    metadata stays serial.
  - If a lane consumes an artifact, symbol, file, API, schema, migration, or
    other interface produced or changed by another lane, the producer runs
    first. Ambiguous producer/consumer relationships or output identities stay
    serial rather than being guessed.
  - Explicit ordering, migrations, shared resources, data-integrity work, and
    other plan-declared sequencing serialize even when files are disjoint.
  - Only tasks with complete disjoint write sets and no interface, shared-state,
    or ordering dependency may share a batch.
- Treat every path a child may create, modify, delete, or generate as part of
  its hard `Files` write allowlist. Reports, planning artifacts, generated
  output, and lockfiles must be explicitly owned or the task stays serial. A
  fixer must return `NEEDS_CONTEXT` or `BLOCKED` rather than write outside its
  allowlist or an active task's ownership.
- Do not create artificial micro-tasks when the work is tiny, tightly coupled,
  or coordination would cost more than the parallelism saves.
- Preserve designer intent across later lanes. Use `@fixer` for follow-up UI
  work only when it is mechanical and does not change visual or interaction
  decisions; route design changes back to `@designer`.

For each batch, dispatch only ready tasks whose required predecessors passed
review. Record the exact returned session ID and job ID for every background
dispatch; wait for all tasks in that same batch, then reconcile with
`task_result` using those exact session IDs rather than aliases. Review each
`DONE` lane within the available reviewer cap, queueing excess reviews; this
cap applies only to reviewer scheduling. Arbitrary conversational tool-call
parallelism remains disallowed. Do not start a dependent batch until every
required predecessor has a successful implementer result and a passing
per-child review (or an explicit @oracle adjudication resolves it).
Unrelated ready work may finish while a failed predecessor is fixed or
escalated, but dependent work waits. `NEEDS_CONTEXT`, `BLOCKED`, timeout,
failure, missing, or malformed reports hold dependents and are surfaced
explicitly. After the batch's lanes finish, reconcile
their terminal reports against the complete plan and combined diff:

1. Map every planned item to a completed specialist result or an explicit
   escalation; do not silently treat partial work as complete.
2. Confirm each lane changed only its assigned files and that overlapping edits
   or conflicts have been resolved.
3. Verify every acceptance criterion and validation result, including any
   designer-to-fixer handoff constraints.
4. Inspect the combined result for missing work, unaddressed concerns, and
   regressions before running final validation.

If an ownership overlap or dependency conflict is discovered after dispatch,
stop the affected lanes before conflicting writes continue and escalate for
re-sequencing. Preserve unrelated completed work; never guess which lane owns
the shared file or output.

Do not declare completion while any relevant lane is missing a report, has
status `NEEDS_CONTEXT` or `BLOCKED`, or has an unverified acceptance criterion.

## SDD Artifact Persistence

- SDD artifacts live outside the working repo at
  `~/developer/planning-docs/{{repository-name}}/.planning/`, where `{{repository-name}}` is the
  current repository directory name:
  `~/developer/planning-docs/{{repository-name}}/.planning/specs/` for design docs and
  `~/developer/planning-docs/{{repository-name}}/.planning/plans/` for implementation plans.
- Before planning or resuming work, check
  `~/developer/planning-docs/{{repository-name}}/.planning/` for existing artifacts and
  use them as context.
- Never create planning artifacts under `docs/.planning/` inside the working
  repo; use the external path above.
- Cross-repo references should use the corresponding repository directory under
  `~/developer/planning-docs/`.

## Development Environment

- **MANDATORY: Follow all rules in `git-safety.md` for any Git or GitHub operation.**
- If a test or lint command fails to run, ask me which command to use and where
  the root folder is, then remember it.
- When tests fail, show me only the errors — filter the console output, don't
  dump it raw.
- Always run lint validation (check-only, no autofix) before finishing an
  implementation. Run lint with autofix only when the handoff explicitly
  includes a `Lint Autofix` directive, and limit autofix to the files listed in
  that directive.

## Package Manager & Monorepo Paths

- Always check which package manager the project uses first — start with `pnpm`.
- For workspace/monorepo commands, the path is relative to the package you're
  working on, not the repo root. e.g.
  `pnpm --filter @gorgias-chat/client test:unit src/foo/Bar.spec.tsx`.

## Commit Messages

- Conventional commits: `type(scope): description`. Types: `feat`, `fix`,
  `docs`, `style`, `refactor`, `test`, `chore`.
- Title ≤ 100 chars, lowercase, present tense ("add feature" not "added
  feature"), no trailing period. If the scope is unclear or there are multiple,
  drop it: `type: description`.
- Never add `Co-Authored-By:` lines or any AI attribution.
- Keep it simple: summarize the changed files, don't explain every detail.
- Reference issue numbers when applicable (#123). Detailed context goes in the
  body if needed.

**Examples**

- Good: `feat(chat): add message retry functionality`
- Good: `fix(bundle): reduce bundle size by removing unused deps`
- Bad: `Added new feature` · `Fixed bug.` · `Update`

## Notion Access

**Never handle Notion directly as the main agent.** Route based on context:
- **Gorgias/internal Notion** (notion.so/gorgias/... or any internal doc) → delegate to `@sage`
- **Public Notion pages** (external, non-Gorgias) → delegate to `@librarian`
- **Never open a Notion link in a browser** — always delegate

**Notion URL → page ID extraction** (for subagents to use):
- URL patterns: `https://www.notion.so/<page-id>` or `https://www.notion.so/<workspace>/<title>-<page-id>[?params]`
- Strip query params, take the last path segment; if it contains `-`, the page ID is everything after the **last** `-`; otherwise the segment itself is the page ID
- Page IDs are 32 lowercase hex chars (UUID without dashes)
- Example: `https://www.notion.so/gorgias/My-Doc-1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d?pvs=4` → ID: `1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d`

## Observability & Troubleshooting

- **Never use Sentry MCP tools directly** (`mcp__sentry__*`) — always delegate
  to the `@detective` subagent.
- **Never run `pup` CLI directly** — always delegate to the
  `@detective` subagent.
- **Never run `gcloud logging` directly** — always delegate to the
  `@detective` subagent.
- Exception: you are the `@detective` subagent itself.

## Browser Interaction

- **Never invoke the `agent-browser` CLI or use `chrome-devtools-mcp` directly** —
  always delegate browser automation to the `@navigator` subagent.
- Exception: you are the `@navigator` subagent itself; Navigator runs
  `agent-browser` through Bash.

## General

- Temporary-file cleanup period: 7 days.

## Commit / Push Safety Scan

- Before any `git commit`, `git push`, or `git rebase` (and on branch switch, or
  when working on a branch with an open PR), read and apply security-scan rules.
- **MANDATORY: Follow all rules in `git-safety.md` for any Git or GitHub operation.**
