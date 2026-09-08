# Workflows

At a review boundary, the orchestrator validates the registry, redacts and
digests one immutable packet, selects applicable focuses, and dispatches fresh
`reviewer` tasks in batches of no more than three. It waits for each batch and
reconciles exact session IDs. A session is never revived for another focus.

Missing packet evidence, coordination failures, malformed results, late
results, permission mismatches, or missing native evidence make the review
health-first verdict inconclusive. Validation evidence remains explicit and
never infers a pass from an absent event.
