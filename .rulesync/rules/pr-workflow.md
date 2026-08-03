---
name: pr-workflow
description: AI rules/agent definition for pr-workflow.md
---

# Pull Request Workflow

## Git & GitHub Safety

**MANDATORY: Follow all rules in `git-safety.md` for any Git or GitHub operation.**

- **Never push**: Provide the command for the user to run.
- **Commit approval**: Always ask before running `git commit`.
- **PRs**: Generate title/description and show the `gh` command; never run it.

## PR Creation & Updates

### General Rules

- **NEVER run `gh pr create` or `gh pr edit`**. Always show the command for me to run manually.
- **Always use `--draft`** by default in the shown command (unless user explicitly says "ready for review")
- **Always add label `claude:review`** to the command (draft or not)

### Title Format

- Use conventional commit format: `type(scope): description`
- `type`: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- `scope`: Optional; drop if unclear or multiple areas affected
- `description`: Lowercase, present tense, ≤100 chars total, no trailing period
- Examples:
  - `feat(auth): add jwt token refresh`
  - `fix: resolve null pointer in data processor`

### Description

- Save to file, **never paste inline**:
  - `.context/pr/<branch-name>.md` if `.context/` exists
  - `/tmp/pr-<branch-name>.md` otherwise
- Format: First line `# <title>`, blank line, then body
- Check for `.github/PULL_REQUEST_TEMPLATE.md` in the target repo
  - If found: reference and follow its structure
  - If not found: use default structure (Overview, Test Plan, Metrics/Context)
- **Keep descriptions lean**: Overview + test plan only
  - NO deep implementation details
  - NO line-by-line code explanations
  - NO architecture discussions (save for commit messages or comments)

### When Updating a PR

- Reuse the same description file from step 1
- Overwrite it with new content
- Provide the exact `gh pr edit` command

## Command Format

Always give the user a copyable command block. Example:

```sh
# Create draft PR with label
gh pr create --base main --draft \
  --title "$(head -1 /tmp/pr-feature-name.md | sed 's/^# //')" \
  --body-file <(tail -n +3 /tmp/pr-feature-name.md) \
  --label claude:review
```

```sh
# Update existing PR
gh pr edit 42 \
  --title "$(head -1 /tmp/pr-feature-name.md | sed 's/^# //')" \
  --body-file <(tail -n +3 /tmp/pr-feature-name.md)
```
