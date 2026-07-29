# Custom Rules (always applied)

## Machine Configuration

- Always use zsh. Before running any command, source my `~/.zshrc` first so the
  environment matches my interactive terminal.

## Workflow (main agent only)

**Simple / straightforward tasks** — implement directly. Write a short inline
plan of action (a quick numbered list of steps), then execute without waiting
for approval.

**Non-trivial tasks** (new features with unknowns, multi-area changes, unclear
root cause) — create a full plan first, show it in digestible chunks, and wait
for "go" before applying.

Subagents execute directly — no planning step required.

## SDD Artifact Persistence

- SDD artifacts live in `docs/.planning/` within the working repo:
  `docs/.planning/specs/` for design docs, `docs/.planning/plans/` for implementation plans.
- Before planning or resuming work, check `docs/.planning/` for existing artifacts and use them as context.
- Cross-repo reference: if you need to reference a spec/plan from another repo, note the path explicitly — no automated centralization.

## Development Environment

- **Never run any git command on your own — always ask and confirm first.** This
  is the single source of truth for git behavior and covers commit, push,
  checkout, rebase, and merge.
- If a test or lint command fails to run, ask me which command to use and where
  the root folder is, then remember it.
- When tests fail, show me only the errors — filter the console output, don't
  dump it raw.
- Always run lint to fix files before finishing an implementation.

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
  Reference issue numbers when applicable (#123). Detailed context goes in the
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
  to the `observability-and-troubleshoot` subagent.
- **Never run `pup` CLI directly** — always delegate to the
  `observability-and-troubleshoot` subagent.
- **Never run `gcloud logging` directly** — always delegate to the
  `observability-and-troubleshoot` subagent.
- Exception: you are the `observability-and-troubleshoot` subagent itself.

## Browser Interaction

- **Never use mcp-server-browser or chrome-devtools-mcp tools directly** —
  always delegate to the `browser-agent` subagent.
- Exception: you are the `browser-agent` subagent itself.

## General

- Temporary-file cleanup period: 7 days.

## Commit / Push Safety

- Before any `git commit`, `git push`, or `git rebase` (and on branch switch, or
  when working on a branch with an open PR), read and apply security-scan rules.
