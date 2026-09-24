# Pi Tool Mapping

Skills speak in actions ("dispatch a subagent", "create a todo", "read a file"). On Pi these resolve to the tools below.

| Action skills request | Pi equivalent |
| --- | --- |
| Dispatch a subagent (`Subagent (general-purpose):` template) | Use an installed subagent tool such as `subagent` from `pi-subagents` if available |
| Task tracking ("create a todo", "mark complete") | Use an installed todo/task tool if available, otherwise track tasks in the plan or `TODO.md` |

## Subagents

Pi core does not ship a standard subagent tool. The `pi-subagents` package is a strong optional companion and provides a `subagent` tool with single-agent, chain, parallel, async, forked-context, and resume/status workflows. If no subagent tool is available, do not fabricate `Task` calls; execute sequentially in the current session or explain that the optional subagent capability is not installed.

## Task lists

Pi core does not ship a standard task-list tool. If a todo/task extension is installed, use its documented tool. Otherwise use Superpowers plan files, checklists in Markdown, or a repo-local `TODO.md` for task tracking. Older Superpowers docs may refer to `TodoWrite`; treat that as the task-tracking action above.

## Pushing code

**Never push without explicit user confirmation.** Before pushing, always:

1. Show what will be pushed — list each commit with its hash and subject line:
   ```
   git log --oneline <upstream-branch>..HEAD
   ```
2. Ask for confirmation, including the target remote and branch.
3. Only push after the user explicitly approves.

This prevents accidental pushes of unfinished work, wrong branches, or commits that weren't meant to go out yet.

## Creating pull requests

**Never create or push a PR directly.** When the user asks for a PR:

1. Inspect the repo's existing PR history to understand the title/description conventions (prefixes, format, sections, issue linking).
2. Generate a title and description following that pattern.
3. **Show the title** first, then **show the full description**.
4. Instead of opening or pushing the PR, **give the user the command to execute themselves** — for example a `gh pr create` invocation or a `git push` command. Let them run it manually.

This keeps the user in control of when code goes out for review.
