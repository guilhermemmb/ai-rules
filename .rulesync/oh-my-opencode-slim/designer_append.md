## Machine Config

- Always use zsh. Source `~/.zshrc` before running commands.
- Git user: Guilherme Bomfim (guilherme.bomfim@gorgias.com).
- Node: Volta (`$VOLTA_HOME/bin`). Package manager: start with pnpm, then check
  project.
- PATH: `$VOLTA_HOME/bin`, `~/.local/bin`, `$PNPM_HOME`, `~/developer/gorgi`.
- `@gorgias` npm scope: registry at `https://npm.pkg.github.com/`.

## Figma Design Spec Collection

See rules: `figma-design-to-code`, `figma-code-connect`, `figma-mcp-server`.

Invoke the following skills:
- figma-design-to-code: Figma-to-code implementation
- figma-code-connect: .figma.ts Code Connect templates
- figma-use: write-to-canvas Plugin API work
- figma-implement-motion: motion translation
- figma-generate-library: design-system library generation

- Use `get_design_context` as primary tool for reading design specs — never
  `get_metadata` or `get_screenshot` as substitutes.
- Adapt Figma output to project's actual framework, component library, and
  design tokens — never copy-paste React+Tailwind verbatim.
- Honor response hints by priority: Code Connect snippets → component docs →
  design annotations → design tokens → raw values.
- Assets expire in ~7 days — download-and-commit for production code.
