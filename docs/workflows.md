# Workflows

For each completed fixer batch, the orchestrator validates the canonical
registry, redacts and digests one immutable batch packet, selects applicable
focuses, and dispatches fresh `reviewer` tasks in batches no larger than the
registry cap of ten. It waits for all focus results and reconciles exact
session IDs. A session is never revived for another focus. The boundary emits
one consolidated batch review report; dependent batches wait until that report
is reconciled.

After all batches are complete, the orchestrator runs one mandatory full-branch
review and retains its final report. Final handoff and commit authorization
require that report. Findings in both reports are report-only: the user chooses
whether to fix, defer, or accept them. A separate Git security scan remains
required before any commit.

Missing packet evidence, coordination failures, malformed results, late
results, permission mismatches, or missing native evidence make the review
health-first verdict inconclusive. Validation evidence remains explicit and
never infers a pass from an absent event.
