---
name: overview
description: AI rules/agent definition for overview
root: true
---


# Global Instructions

## Branch Naming

- Always use `guilhermebomfim/` as the prefix (e.g.
  `guilhermebomfim/feature-name`), never `guilhermemmb/`

## Git & GitHub Safety

**MANDATORY: Follow all rules in `git-safety.md` for any Git or GitHub operation.**

- **Never push**: Provide the command for the user to run.
- **Commit approval**: Always ask before running `git commit`.
- **PRs**: Generate title/description and show the `gh` command; never run it.
- **GitHub API**: Read-only mode for all `gh` commands.

## Forbidden Commands

- **NEVER run `gh run rerun`** or any command that triggers GitHub workflow runs
- The `collect` commands in gh-actions-metrics are read-only only

## PR Workflow

When asked to "create PR", "open PR", "update PR", "draft PR", or similar, follow the process in `git-safety.md` and `pr-workflow.md`.
