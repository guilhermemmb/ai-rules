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

## OpenSpec Persistence

- After every SDD archive step, copy the archived change directory to
  `/Users/guilhermebomfim/developer/gorgias-power-project/<repo>/openspec/`,
  where `<repo>` is the repo currently being worked on. Create the dir if
  absent.
- This applies EVEN when the working directory is a repo elsewhere — never write
  these artifacts into the repo itself; always centralize them under the path
  above.
- READ from there too: before planning or resuming work on a repo, check
  `.../gorgias-power-project/<repo>/openspec/` for existing change artifacts and
  use them as context.

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

- **Never use Notion MCP tools or APIs directly** — always delegate to the `cortex` subagent and have it use the cortex MCP server for all Notion access.
- Exception: you are the `cortex` subagent itself.

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
