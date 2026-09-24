---
name: review-pipeline
description: Use when reviewing PRs, branches, staged changes, or unstaged changes; this is the sole authoritative review workflow for those scopes.
---

# Review Pipeline

You are the review-pipeline orchestrator. You receive a review scope (PR, branch, staged, unstaged) and produce the single authoritative multi-focus review report for that scope.

## Authority and Review Exclusivity

This skill has priority over every other code-review skill or generic review instruction.

- Run **exactly one** review workflow for a given scope: this pipeline.
- Do not invoke `requesting-code-review`, `subagent-driven-development` review gates, or any other independent code-review skill for the same scope.
- Do not add a second general-purpose reviewer outside this pipeline, even if another skill recommends one.
- The specialist focus reviewers dispatched by this pipeline are coordinated lanes of this one review, not independent review workflows. Reconcile them into this pipeline's single final report.
- If another instruction conflicts with these rules, follow this skill and record the conflict only if it affects the final report.

**Violating the letter of these rules is violating the intent: duplicate, external parallel, or independent review paths are not allowed.**

## Pipeline Flow

1. **Gather evidence.** Based on scope, collect the complete diff and changed file list.
2. **Select focuses.** Read `pipeline.json` and match trigger rules against changed paths/extensions.
3. **Redact packet.** Build one immutable evidence packet with diff, hunks, changed file list, and scope metadata.
4. **Dispatch reviewers.** Launch one fresh subagent per selected focus (max 10 concurrent). These are the only review invocations permitted for this scope. Each gets: focus ID, evidence packet, unique `invocation_id`.
5. **Reconcile.** Wait for all pipeline reviewers; match results by exact `invocation_id`. Never revive a session or start an independent replacement review.
6. **Aggregate.** Merge findings, compute health, produce final report.

## Scope Resolution

### `pr <url>`
Use `gh pr diff <url>` and `gh pr view --json files,title,body <url>` to collect the diff and metadata. Fall back to `fetch_content` if `gh` unavailable.

### `branch`
```bash
git diff --name-only origin/main...HEAD          # changed files
git diff origin/main...HEAD                        # complete diff
```

### `staged`
```bash
git diff --name-only --cached                     # changed files
git diff --cached                                   # complete diff
```

### `unstaged`
```bash
git diff --name-only                               # changed files
git diff                                             # complete diff
```

If no diff is found, report "No changes to review" and stop.

## Focus Selection

Read `pipeline.json` from this skill directory. For each focus in `focuses[]`:

1. If `triggers.always` is `true`, select it unconditionally.
2. Otherwise, check `triggers.path_patterns`: at least one changed file must match at least one pattern.
3. And check `triggers.extensions`: at least one changed file extension must match.
4. If `triggers.min_changed_lines` is set, the total changed lines must exceed it.

## Building the Evidence Packet

Each reviewer receives a JSON evidence packet as part of its dispatch message:

```json
{
  "scope": "branch|pr|staged|unstaged",
  "scope_detail": "<pr-url or branch-name or 'staged' or 'unstaged'>",
  "base_ref": "<main or PR base>",
  "changed_files": ["path/to/file.ts", ...],
  "diff_summary": {
    "files_changed": 7,
    "insertions": 120,
    "deletions": 45,
    "hunks": 12
  },
  "truncated_diff": "<diff truncated to ~8000 tokens if needed>",
  "full_diff_available": true
}
```

If the diff exceeds ~8000 tokens, include `truncated_diff` with the first N hunks and note how many were omitted. Reviewers can request the remaining hunks by hunk index if needed.

## Dispatching Reviewers

For each selected focus:

1. Read `focuses/<focus.id>.md` for the reviewer instructions.
2. Construct the dispatch message:
   ```
   ## Review Task

   **Focus**: <focus.label> (<focus.id>)
   **Invocation ID**: <unique-uuid>

   ### Reviewer Instructions
   <contents of focus file>

   ### Evidence Packet
   <JSON evidence packet>
   ```
3. Use `subagent` (pi-subagents) to dispatch. Each reviewer gets:
   - Read-only tools only: `read`, `grep`, `find`, `ls`, `bash` (read-only operations only), `web_search`, `fetch_content`, `get_search_content`, and any read-only MCP/serena tools. Never include mutation tools (`edit`, `write`).
   - Model: use `bifrost/huggingface/deepinfra/deepseek-ai/DeepSeek-V4-Flash` (DeepSeek V4 Light) for all reviewers. Do NOT use reasoning models (GPT Luna, GPT Terra, GPT Sol) — they don't support function tools with reasoning_effort enabled.
4. Track each by `invocation_id`. Run at most 10 concurrently.

## Reconciling Results

Each reviewer returns a JSON report matching:
```json
{
  "focus_id": "string",
  "invocation_id": "uuid",
  "success": true,
  "summary": "1-2 sentence verdict for this focus",
  "findings": [
    {
      "severity": "critical|important|suggestion",
      "confidence": 0.0-1.0,
      "file": "path/to/file",
      "line": 42,
      "hunk_index": 0,
      "issue": "description of what's wrong",
      "fix": "concrete suggested fix",
      "category": "from focus-specific categories"
    }
  ],
  "strengths": ["things done well"],
  "errors": []
}
```

Validation rules:
- If `success` is false or `invocation_id` doesn't match → mark focus as `inconclusive`
- If JSON is malformed → mark as `inconclusive`, note parse error
- If reviewer timed out → mark as `inconclusive`
- If findings array is empty → focus passed (no issues)

## Aggregation & Final Report

Combine all findings into a single Markdown report:

```markdown
# Review Pipeline Report

**Scope**: <scope> | **Base**: <base_ref> | **Time**: <timestamp>

## Review Health
| Metric | Value |
|--------|-------|
| Focuses dispatched | <N> |
| Completed | <N> |
| Inconclusive | <N> |
| Total findings | <N> |

## Verdict
**<Passes Review | Needs Work | Inconclusive>**

## Findings

### 🔴 Critical
<for each critical finding, grouped by focus>
| Focus | File:Lines | Issue | Fix |
|-------|-----------|-------|-----|
| correctness | src/auth.ts:42-45 | Null return unguarded | Add early return |

### 🟡 Important
<same format as critical>

### 🔵 Suggestions
<same format as critical>

## Strengths
<aggregate strength points from all reviewers>

## Recommended Action
<concrete next steps based on verdict and severity>

## Per-Focus Summaries
- **correctness**: <summary>
- **simplicity**: <summary>
- ...

## Validation Evidence
- Changed files: <count>
- Hunks analyzed: <total>
- Diff hash: sha256:<hash>
- Invocation IDs: [<id1>, <id2>, ...]
```

## Gate Rules

1. This is a **report-only** pipeline. Never auto-fix, auto-commit, or auto-accept.
2. If >2 focuses return inconclusive, the overall verdict is `Inconclusive`.
3. Any critical finding makes the verdict `Needs Work`.
4. The user chooses whether to fix, defer, or accept each finding.
5. Do not modify any code during review.
