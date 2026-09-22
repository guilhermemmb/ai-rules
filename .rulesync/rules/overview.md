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

- Follow `git-safety.md`, the authoritative source for Git and GitHub safety,
  including push, commit, PR mutation, and GitHub API restrictions.

## Forbidden Commands

- **NEVER run `gh run rerun`** or any command that triggers GitHub workflow runs
- The `collect` commands in gh-actions-metrics are read-only only

## PR Workflow

When asked to "create PR", "open PR", "update PR", "draft PR", or similar, follow the process in `git-safety.md` and `pr-workflow.md`.
