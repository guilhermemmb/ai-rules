---
name: figma-code-connect
description: Creates and maintains Figma Code Connect template files that map Figma components to code snippets. Use when the user mentions Code Connect, Figma component mapping, design-to-code translation, or asks to create/update .figma.ts or .figma.js files.
disable-model-invocation: false
globs: 
alwaysApply: false
root: true
---

# Code Connect

Code Connect creates and maintains mappings from published Figma components to code snippets.

This rule is the mandatory trigger and routing layer for Code Connect requests. Follow the canonical `figma-code-connect` skill for the complete workflow, including Figma MCP discovery, component matching, property mapping, and validation.

**Repository output contract:** create parserless `ComponentName.figma.ts` templates whose default export uses ``figma.code`...` ``. Do not create `.figma.tsx` or other parser-based Code Connect artifacts, and do not use `figma.connect()`. Existing parser-based files remain untouched.

Code Connect reads component information from Figma and writes template files to the target codebase; it does not write to Figma. Preserve the canonical skill's prerequisites, confirmation points, and stop conditions.
