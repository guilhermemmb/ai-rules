---
description: "**MANDATORY prerequisite** — you MUST invoke this skill BEFORE calling the `get_design_context` Figma MCP tool. You MUST trigger this skill whenever the user wants to implement, build, port, or code up a Figma design as code. Example prompts (not exhaustive) are 'implement this Figma design', 'build this screen from Figma', 'turn this Figma into code', 'design to code'. This skill provides critical instructions and steps to the agent on how to correctly implement Figma designs in code and must NOT be skipped."
globs: 
alwaysApply: false
root: true
---

# Implement a Figma Design as Code (Design → Code)

This rule is the mandatory trigger and routing layer for implementing, translating, or porting a Figma design into code. Before calling `get_design_context`, invoke the canonical `figma-design-to-code` skill and include `figma-design-to-code` in the comma-separated `skillNames` parameter (prefix it with `resource:` when loaded through an MCP resource).

The design-to-code direction reads design context and assets from Figma, then adapts them to the target codebase. It must not write to Figma; Figma writes belong to `figma-use`. Follow the canonical `figma-design-to-code` skill for URL handling, reuse of project components and tokens, asset handling, responsive behavior, and validation. Do not substitute screenshots or metadata for the required `get_design_context` call, and ask for a node-specific URL when no `node-id` is provided.

Before completion, perform a mandatory final validation gate covering layout, typography, colors, interaction states, responsive behavior, assets, and accessibility.
