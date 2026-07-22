# Rules Guide

How rules are organized, where they live, and how to update them.

---

## Rule Files at a Glance

| File | Always Loaded | Purpose |
|------|:---:|---------|
| `CLAUDE.md` | ✅ | Master instructions — everything an LLM needs to work correctly |
| `.rulesync/rules/overview.md` | ✅ | GitHub/PR/git push rules (distributed root file) |
| `.rulesync/rules/custom-rules.md` | ✅ | Workflow: planning, commits, tests, packages |
| `.rulesync/rules/user-config.md` | ✅ | Machine config: env vars, git config, shell aliases |
| `.rulesync/rules/security-scan.md` | ❌ on-demand | Security checklist for commit/push/rebase |

**On-demand** means the rule is not always loaded — it's applied when a trigger fires (git commit, push, rebase, branch switch, or open PR).

---

## Domain Map

| Domain | Lives in |
|--------|---------|
| Git safety (push, force, read-only) | `overview.md` |
| PR creation & description | `overview.md` |
| Workflow (plan first, shell, superpowers) | `custom-rules.md` |
| Commits (format, no co-author) | `custom-rules.md` |
| Tests (log output, re-run policy) | `custom-rules.md` |
| Packages (pnpm, monorepo paths) | `custom-rules.md` |
| Machine config (env, aliases, git config) | `user-config.md` |
| Security scan (mock data, secrets, debug) | `security-scan.md` |

**One rule, one domain.** If a rule covers two domains, put it in the more specific file and reference it from the other.

---

## Rule Organization Principles

1. **No duplication** — If the same rule appears in two files, remove it from the less-authoritative one. `CLAUDE.md` is the authoritative human-readable source; `.rulesync/rules/` is the machine-distributed source.

2. **Sorted by frequency** — Most-triggered rules appear first within each section. Git safety > workflow > config.

3. **Imperative, not explanatory** — Rules say what to do, not why. Save the "why" for a comment only if truly non-obvious.

4. **Tables over prose** — Use tables for lists of allowed/blocked items, categories, keywords.

5. **Explicit triggers** — On-demand rules state clearly when they fire (e.g. "Load before any `git commit`").

---

## How to Add a New Rule

1. Identify the domain → pick the right file from the domain map above
2. Add the rule in the appropriate section, sorted by frequency
3. If it's a security/safety rule → add to `security-scan.md` instead
4. Mirror it in `CLAUDE.md` under the same section header
5. Run rulesync to distribute

---

## How to Update an Existing Rule

1. Edit the `.rulesync/rules/<file>.md` source
2. Update the corresponding section in `CLAUDE.md`
3. Run rulesync

**Never edit the rulesync *output* files directly** (`.claude/rules/`, `.opencode/memories/`, etc.) — they're overwritten on the next sync.

---

## Rulesync Output Locations

| Target | Output Directory |
|--------|----------------|
| Claude Code | `.claude/rules/` |
| OpenCode | `.opencode/memories/` |
| Codex CLI | `.codex/` + `AGENTS.md` |
| Zed | `.zed/` |
| Warp | `.warp/` |
