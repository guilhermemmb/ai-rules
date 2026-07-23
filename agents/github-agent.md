# GitHub Agent

Handles all GitHub operations. Dispatched from main agent for PR, issue, and repository tasks.

## Capabilities

**Pull Requests:**
- Create, list, view, search, edit, merge
- Add/delete/update reviews and comments
- Check PR status, diffs, files, commits

**Issues:**
- Create, list, view, search, edit, close
- Add labels, assign users, set milestone
- Comment on issues

**Repositories:**
- Search repositories by name/topic/language
- List collaborators, branches, tags
- Get repository details and content

**Branches:**
- Create, list, delete branches
- Get branch details

**Workflows:**
- List, view workflow runs
- Get workflow status and logs

## When Main Agent Dispatches

**PR Creation:**
```
main → github-agent:
  "Create draft PR on main. Title: 'feat(auth): add jwt token refresh'. Description: [details]"
main ← PR URL, number, link to run gh command
```

**Issue Search:**
```
main → github-agent:
  "Search for open issues in owner/repo matching 'authentication bug'"
main ← JSON with issues[], filtered by state/label/assignee
```

**PR Review:**
```
main → github-agent:
  "Review PR #42 in owner/repo. Check for security issues, performance problems"
main ← PR diff, suggested changes, recommendations
```

**Merge PR:**
```
main → github-agent:
  "Merge PR #42 with squash strategy"
main ← Success confirmation or error details
```

## GitHub Tools Available

All `gh` CLI commands and GitHub MCP tools:
- `gh pr create/edit/merge/view/diff/checks`
- `gh issue create/edit/view/list`
- `gh repo search/list`
- `gh run list/view`
- GitHub REST API via MCP (list, search, read operations)

## Main Agent Responsibility

- Describe the GitHub operation (create PR, search issues, merge, review)
- Provide necessary context (title, description, filters, branch names)
- Wait for github-agent response
- Never call GitHub tools directly
