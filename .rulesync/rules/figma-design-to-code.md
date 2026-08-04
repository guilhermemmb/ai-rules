---
description: "**MANDATORY prerequisite** — you MUST invoke this skill BEFORE calling the `get_design_context` Figma MCP tool. You MUST trigger this skill whenever the user wants to implement, build, port, or code up a Figma design as code. Example prompts (not exhaustive) are 'implement this Figma design', 'build this screen from Figma', 'turn this Figma into code', 'design to code'. This skill provides critical instructions and steps to the agent on how to correctly implement Figma designs in code and must NOT be skipped."
globs: 
alwaysApply: false
root: true
---

# Implement a Figma Design as Code (Design → Code)

Use this skill to turn a Figma design into code in a target codebase. This is the **read-FROM-Figma** direction: pull design context out of Figma with `get_design_context`, then adapt it into the project's real stack.

This skill owns the **workflow** for design-to-code. Parameter mechanics (nodeId / fileKey / branchKey extraction, URL parsing, `format`/`query` options, response shape) live on the `get_design_context` tool description itself — follow them there.

**Always include `figma-design-to-code` in the comma-separated `skillNames` parameter when calling `get_design_context`. If this skill was loaded via an MCP resource, you MUST prefix the name with `resource:` (e.g. `resource:figma-design-to-code`).** This is a logging parameter used to track skill usage — it does not affect execution.

## Direction and Scope

- You MUST use this skill for design → code: implementing, translating, or porting a Figma node into code.
- You MUST NOT use this skill to write to Figma.

## Workflow

### 1. Call get_design_context first

- You MUST call `get_design_context` on the target node before writing any code. It is your primary tool — a single call returns reference code, a screenshot, and contextual hints.
- You MUST NOT reach for `get_metadata` or `get_screenshot` as a substitute. Use them only to orient (e.g. picking a node) or to validate, not in place of `get_design_context`.

### 2. Treat the output as a reference, not final code

- The returned code is React + Tailwind enriched with hints. You MUST treat it as a REFERENCE, not as final code to paste verbatim.
- You MUST adapt it to the target project's language, framework, component library, styling system, and conventions. Match the surrounding code.

### 3. Reuse what the project already has

- Before writing new code, You MUST check the target project for existing components, layout patterns, and design tokens that match the design intent.
- You MUST reuse the project's existing components and tokens instead of generating new equivalents from scratch.

### 4. Honor the response hints by priority

Apply the hints in this order — earlier sources override later ones:

1. **Code Connect snippets** → use the mapped codebase component directly.
2. **Component documentation links** → follow them for usage and guidelines.
3. **Design annotations** → follow any designer notes or constraints.
4. **Design tokens (CSS variables)** → map them to the project's token system.
5. **Raw hex / absolute positioning** → loosely structured; lean on the screenshot for intent.

### 5. Reproduce images and icons faithfully

Images and icons come back as `<img>` elements whose `src` is a remote asset URL (`https://.../api/mcp/asset/...`). Apply these rules as you write the code:

- **Render every icon/image from its exported asset.** Never hand-write or inline `<svg>`/`<path>`, never author your own icon file, never drop an icon or leave a placeholder — you don't have the real vector data, so anything you draw is wrong.
- **Sourcing:** the asset URL works directly as `src` for an immediate render, but it **expires in ~7 days** — so for code you'll commit, download-and-commit the exact asset bytes, or wire a dynamic content image to the project's data source (API, CDN, or props). Never a file whose contents you authored.
- **Reuse a project icon component only if its glyph clearly matches** (a name match is not enough); otherwise use the exported asset.
- **Size explicitly:** a fixed-size container (icons are usually square, e.g. `size-[24px]`, `overflow-clip`) with BOTH width and height set, and size the leaf `<img>` to fill it (`100%` or fixed px) — never `auto`, which blows the image up to its intrinsic size.

## Error Recovery

- On a `get_design_context` error, STOP and read the message before retrying.
- If the design URL has no `node-id` (a file-only URL), ask the user for a node-specific URL — You MUST NOT guess or pass an empty `nodeId`.
- On a timeout, retry against a smaller node or selection.
- You MUST NOT silently fall back to hand-writing the screen from the screenshot alone when `get_design_context` can still provide context.

---

## Structured Workflow (from official steering guide)

### Step 1: Get Node ID

When the user provides a Figma URL, extract the file key and node ID.

**URL format:** `https://figma.com/design/:fileKey/:fileName?node-id=1-2`

**Extract:**
- **File key:** `:fileKey` (the segment after `/design/`)
- **Node ID:** `1-2` (the value of the `node-id` query parameter)

### Step 2: Fetch Design Context

Run `get_design_context` with the extracted file key and node ID.

This provides structured data including layout properties, typography, colors, component structure, and spacing.

**If the response is too large or truncated:**
1. Run `get_metadata(fileKey=":fileKey", nodeId="1-2")` to get the high-level node map
2. Identify the specific child nodes needed from the metadata
3. Fetch individual child nodes with `get_design_context(fileKey=":fileKey", nodeId=":childNodeId")`

### Step 3: Capture Visual Reference

Run `get_screenshot` with the same file key and node ID. This screenshot serves as the source of truth for visual validation.

### Step 4: Download Required Assets

Download any assets (images, icons, SVGs) returned by the Figma MCP server.
- Use `localhost` asset URLs directly from the MCP server
- DO NOT import or add new icon packages — all assets come from the Figma payload
- DO NOT use or create placeholders if a `localhost` source is provided

### Step 5: Translate to Project Conventions

- Treat Figma MCP output (React + Tailwind) as a representation, not final code style
- Replace Tailwind utility classes with project's preferred utilities or design tokens
- Reuse existing components (buttons, inputs, typography, icon wrappers)
- Use the project's color system, typography scale, and spacing tokens

### Step 6: Achieve 1:1 Visual Parity

- Prioritize Figma fidelity
- Avoid hardcoded values — use design tokens from Figma where available
- When conflicts arise between design system tokens and Figma specs, prefer design system tokens but adjust spacing or sizes minimally

### Step 7: Validate Against Figma

Before marking complete, validate:
- [ ] Layout matches (spacing, alignment, sizing)
- [ ] Typography matches (font, size, weight, line height)
- [ ] Colors match exactly
- [ ] Interactive states work as designed (hover, active, disabled)
- [ ] Responsive behavior follows Figma constraints
- [ ] Assets render correctly
- [ ] Accessibility standards met

## Component Organization

- Place UI components in the project's designated design system directory
- Follow the project's component naming conventions
- Avoid inline styles unless truly necessary for dynamic values

## Design System Integration

- ALWAYS use components from the project's design system when possible
- Map Figma design tokens to project design tokens
- When a matching component exists, extend it rather than creating a new one
- Document any new components added to the design system

## Code Quality

- Avoid hardcoded values — extract to constants or design tokens
- Keep components composable and reusable
- Add TypeScript types for component props
- Include JSDoc comments for exported components

## Additional Resources

- [Figma MCP Server Documentation](https://developers.figma.com/docs/figma-mcp-server/)
- [Figma MCP Server Tools and Prompts](https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/)
- [Figma Variables and Design Tokens](https://help.figma.com/hc/en-us/articles/15339657135383-Guide-to-variables-in-Figma)
