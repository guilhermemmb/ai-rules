---
name: custom-rules
description: Custom rules always applied — machine config, workflow, superpowers persistence, git safety, testing, monorepo paths
metadata:
  type: rule
---

# Custom Rules (always applied)

## Machine Configuration
- Always use zsh. Before running any command, source my `~/.zshrc` first so the environment
  matches my interactive terminal.

## Workflow
- Create a plan first. Show me the plan in digestible chunks and wait for my "go" before
  applying it.

## Superpowers Persistence
- Persist ALL Superpowers artifacts (brainstorming notes, plans, design docs, skill outputs)
  under `/Users/guilhermebomfim/developer/gorgias-power-project/<repo>/superpowers/`, where
  `<repo>` is the repo currently being worked on.
- This applies EVEN when the working directory is a repo elsewhere — never write these artifacts
  into the repo itself; always centralize them under the path above.
- READ from there too: before brainstorming, planning, or resuming work on a repo, check
  `.../gorgias-power-project/<repo>/superpowers/` for existing artifacts and use them as context.
- Compose both sources: combine the repo itself (code, docs, in-repo artifacts) WITH the
  centralized artifacts at that path — read them together, not one or the other.

## Development Environment
- **Never run any git command on your own — always ask and confirm first.** This is the single
  source of truth for git behavior and covers commit, push, checkout, rebase, and merge.
- If a test or lint command fails to run, ask me which command to use and where the root folder
  is, then remember it.
- When tests fail, show me only the errors — filter the console output, don't dump it raw.
- Always run lint to fix files before finishing an implementation.

## Package Manager & Monorepo Paths
- Always check which package manager the project uses first — start with `pnpm`.
- For workspace/monorepo commands, the path is relative to the package you're working on, not the
  repo root. e.g. `pnpm --filter @gorgias-chat/client test:unit src/foo/Bar.spec.tsx`.

## Commit Messages
- Conventional commits: `type(scope): description`. Types: `feat`, `fix`, `docs`, `style`,
  `refactor`, `test`, `chore`.
- Title ≤ 100 chars, lowercase, present tense ("add feature" not "added feature"), no trailing
  period. If the scope is unclear or there are multiple, drop it: `type: description`.
- Never add `Co-Authored-By:` lines or any AI attribution.
- Keep it simple: summarize the changed files, don't explain every detail. Reference issue
  numbers when applicable (#123). Detailed context goes in the body if needed.

**Examples**
- Good: `feat(chat): add message retry functionality`
- Good: `fix(bundle): reduce bundle size by removing unused deps`
- Bad: `Added new feature` · `Fixed bug.` · `Update`

## Observability & Troubleshooting
- **Never use Sentry MCP tools directly** (`mcp__sentry__*`) — always delegate to the `gorgias-troubleshoot` subagent.
- **Never run `pup` CLI directly** — always delegate to the `gorgias-troubleshoot` subagent.
- **Never run `gcloud logging` directly** — always delegate to the `gorgias-troubleshoot` subagent.
- Exception: you are the `gorgias-troubleshoot` subagent itself.

## Browser Interaction
- **Never use chrome-devtools MCP tools directly** (navigate_page, take_screenshot, click, fill, evaluate_script, etc.) — always delegate to the `browser-agent` subagent.
- **Never run `npx agentic-browser` or `agentic-browser` CLI directly** — always delegate to the `browser-agent` subagent.
- Exception: you are the `browser-agent` subagent itself.

## General
- Temporary-file cleanup period: 15 days.

## Commit / Push Safety
- Before any `git commit`, `git push`, or `git rebase` (and on branch switch, or when working on
  a branch with an open PR), read and apply security-scan rules.
