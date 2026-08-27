---
name: context7
description: Trigger-loaded Context7 workflow for library, API, and public documentation questions
globs:
alwaysApply: false
root: true
---

# Context7 MCP — Library Documentation

This rule is trigger-loaded for library, framework, SDK, API, CLI, cloud-service,
and public documentation questions. It is not part of the universal default
context. Use Context7 to fetch current documentation, even for well-known
libraries, because training data may not reflect recent changes.

Do not use for: refactoring, writing scripts from scratch, debugging business
logic, code review, or general programming concepts.

## Steps

1. Always start with `resolve-library-id` using the library name and the user's
   question, unless the user provides an exact library ID. Exact IDs use the
   `/org/project` format; versioned IDs use `/org/project/version`.
2. Pick the best match by: exact name match, description relevance, code snippet
   count, source reputation (High/Medium preferred), and benchmark score
   (higher is better). If results don't look right, try alternate names or
   queries (e.g., "next.js" not "nextjs", or rephrase the question). Use a
   versioned ID when the user mentions a version.
3. `query-docs` with the selected library ID and the user's full question (not
   single words), covering one concept per query. If the question spans multiple
   distinct concepts (e.g. routing and auth and caching), make a separate
   `query-docs` call per concept with the same library ID; combined queries
   dilute ranking and return shallow results for each topic.
4. Answer using the fetched docs

## Failure and fallback

If Context7 is unavailable, authentication fails, or rate limits prevent a
successful lookup, say so explicitly. Use an appropriate fallback, such as
websearch or clearly identified general knowledge, and do not claim that current
Context7 documentation was fetched.
