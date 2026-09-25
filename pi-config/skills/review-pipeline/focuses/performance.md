# Performance Focus

Apply this lens as the predefined reviewer. Follow the shared
[report contract](../contracts.md) and [schema](../report.schema.json), including
severity, coverage, evidence, impact, and report-only rules. Do not orchestrate
additional reviews. Model, thinking, tools and safety are agent-owned.

## Investigate
- Algorithmic growth on realistic input sizes; avoidable repeated computation.
- N+1 queries, redundant fetches, missing batching/pagination and blocking I/O.
- Sequential independent work with materially worse latency; verify dependencies
  and rate/resource limits before recommending parallel execution.
- Unbounded collections, event/timer leaks, allocation and cloning on hot paths.
- Expensive rendering, layout thrashing, large lists and bundle-size regressions.
- Heavy dependencies and ineffective tree-shaking or lazy-loading boundaries.

Support impact with a reachable hot path, meaningful workload bounds or measured
evidence. Missing React.memo/useMemo/useCallback is not itself a defect; do not
recommend memoization or moving derived render calculations into effects without
justification. Explain evidence limits rather than claiming a benchmark ran.
Ignore unmeasurable micro-optimizations and infrastructure outside the change.

Categories: `n-plus-one`, `algorithm`, `memory`, `rendering`, `bundle`, `io`,
`blocking`.
