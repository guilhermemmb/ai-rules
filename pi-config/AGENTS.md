<!-- 2026-09-23 11:26:47 [01a0cdc6] -->
Skill installation in Pi:
To install skills in Pi, follow these steps:
1. Organize each skill in its directory with a `SKILL.md` file.
2. Provide the skill description and usage instructions in `SKILL.md`.
3. Place the skill in the `~/.agents/skills/` or `.agents/skills/` directories which are recursively discovered by Pi.
4. Ensure skills' paths match their declared names for portability across different implementations.
5. Skills are loaded when mentioned in tasks or manually via `/skill:<name>` command.

<!-- 2026-09-23 11:36:46 [01a0cdd4] -->


<!-- 2026-09-23 11:38:40 [01a0cdd4] -->

<!-- 2026-09-23 [mcp-config] -->
Tool Configuration:
- `serena`: Provided natively via `@bacnh85/pi-serena` package in Pi (`serena_*` tools). The `serena` MCP entry was **removed** from `~/.pi/agent/mcp.json` — the extension is self-contained (embeds Serena's Python bridge directly, no MCP protocol) and would collide with MCP's `serena_*` tool names.
- `context7`: Configured with `"directTools": true` in `~/.pi/agent/mcp.json` so its documentation query tools (`context7_resolve-library-id`, `context7_query-docs`) are directly and always exposed.


<!-- 2026-09-23 11:40:33 [01a0cdd4] -->

<!-- 2026-09-23 [pi-default-model] -->
Pi default model set to `bifrost/huggingface/deepinfra/deepseek-ai/DeepSeek-V4-Pro` (DeepSeek Pro) via `~/.pi/agent/settings.json` (`defaultProvider`, `defaultModel`). Ctrl+P / Shift+Ctrl+P model cycling unbound via `~/.pi/agent/keybindings.json` (`app.model.cycleForward`/`cycleBackward` set to `[]`), and `enabledModels` restricted to only DeepSeek-V4-Pro so `/model` and cycling cannot accidentally switch models.


<!-- 2026-09-23 11:41:13 [01a0cdd4] -->

<!-- 2026-09-23 [pi-model-config-update] -->
Update: `enabledModels` restriction was removed per user request — the `/model` picker and `Ctrl+L` selector must show all available models. Only the keybinds are disabled: `app.model.cycleForward`/`app.model.cycleBackward` set to `[]` in `~/.pi/agent/keybindings.json`. Default model remains `bifrost/huggingface/deepinfra/deepseek-ai/DeepSeek-V4-Pro`.


<!-- 2026-09-23 11:58:22 [01a0cdd4] -->

<!-- 2026-09-23 [superpowers-planning-path] -->
Planning artifact override: Created `~/.pi/agent/AGENTS.md` (versioned at `pi-config/AGENTS.md` in ai-rules).
When superpowers skills instruct saving to `docs/superpowers/`, they now redirect to `~/developer/planning-docs/<repo>/.planning/`:
- `docs/superpowers/specs/` → `planning-docs/<repo>/.planning/specs/`
- `docs/superpowers/plans/` → `planning-docs/<repo>/.planning/plans/`
- `sdd-workspace/` → `planning-docs/<repo>/.planning/reports/`
- Ledgers → `planning-docs/<repo>/.planning/ledger-<plan>.md`

This follows Superpowers v5.0+ contract: user instructions in AGENTS.md/CLAUDE.md take precedence over skill defaults. Plans/specs/reports are never committed to project repos.


<!-- 2026-09-23 12:35:00 [01a0ce07] -->
#pi-config #preference

Every time changes are made to Pi global config files (under `~/.pi/agent/`), they must be synced/copied to `~/developer/dotfiles/ai-rules/pi-config/` to keep the backup in the ai-rules repo up to date. This includes settings.json, keybindings.json, mcp.json, models.json, AGENTS.md, and any skill files under `~/.pi/agent/git/` or `~/.pi/agent/skills/`.

<!-- 2026-09-23 13:59:41 [01a0ce58] -->
#decision #preference [[git-workflow]] [[pi-behavior]]

When making code changes that should be committed:
1. **Stage** files with `git add` first — do NOT commit directly without user review.
2. **Summarize** the staged diff (e.g., `git diff --staged --stat` plus a brief natural-language summary of what changed per file). Do NOT show the full diff — the user prefers to navigate the tree themselves.
3. **Ask for confirmation** before committing. Never commit without the user explicitly approving the staged changes.

This applies to all projects, not just the current one.


<!-- 2026-09-23 14:19:15 [01a0ce58] -->
#preference #decision [[superpowers-workflow]] [[planning]]

**Superpowers is the default workflow.** Before taking ANY action that involves planning, implementing, building, designing, or modifying code:

1. **Gate check**: Is this a planning/implementation/building/designing/code-modification request?
   - **Trivial** (small fix, config tweak, one-liner): ask "Use superpowers or just do it directly?"
   - **Non-trivial** (feature, refactor, multi-file change, anything with design decisions): run superpowers (brainstorming → writing-plans → executing-plans) unless the user explicitly says "skip superpowers" or "just do it."
2. **Never self-determine** that superpowers is unnecessary without asking. When in doubt about triviality, ask.

This applies to all projects.
