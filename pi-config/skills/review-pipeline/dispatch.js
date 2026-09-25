// pi-subagents workflowScriptPath body, not a standalone Node program.
// Agent configuration owns model, thinking, tools and safety policy.
if (!Array.isArray(args.lanes) || args.lanes.length === 0) {
  throw new Error('lanes must be a non-empty array');
}
if (!Number.isInteger(args.maxConcurrency) || args.maxConcurrency < 1 || args.maxConcurrency > 10) {
  throw new Error('maxConcurrency must be an integer from 1 to 10');
}
if (!args.reportSchema || args.reportSchema.type !== 'object') {
  throw new Error('reportSchema must be the shared report schema');
}
if (typeof args.packetDigest !== 'string' || !args.packetDigest.startsWith('sha256:')) {
  throw new Error('packetDigest must identify the frozen evidence');
}
const focuses = new Set();
const invocations = new Set();
for (const lane of args.lanes) {
  if (!lane || typeof lane.focusId !== 'string' || !/^[a-z][a-z0-9-]*$/.test(lane.focusId)) {
    throw new Error('invalid focusId');
  }
  if (typeof lane.invocationId !== 'string' || !lane.invocationId.trim()) {
    throw new Error('invalid invocationId');
  }
  if (typeof lane.task !== 'string' || !lane.task.trim()) {
    throw new Error('task must contain the review contract and evidence references');
  }
  if (focuses.has(lane.focusId) || invocations.has(lane.invocationId)) {
    throw new Error('duplicate focusId or invocationId');
  }
  focuses.add(lane.focusId);
  invocations.add(lane.invocationId);
}
const completed = [];
for (let start = 0; start < args.lanes.length; start += args.maxConcurrency) {
  const batch = args.lanes.slice(start, start + args.maxConcurrency);
  const results = await runs.all(batch.map(lane => ({
    key: lane.focusId,
    label: `Review ${lane.focusId}`,
    agent: 'reviewer',
    context: 'fresh',
    task: `${lane.task}\n\nCorrelation: focus_id=${lane.focusId}; invocation_id=${lane.invocationId}; packet_digest=${args.packetDigest}`,
    outputSchema: args.reportSchema,
  })));
  if (!Array.isArray(results) || results.length !== batch.length) {
    throw new Error('runner results missing or incomplete; inspect workflow receipts');
  }
  for (let index = 0; index < batch.length; index++) {
    const lane = batch[index];
    const result = results[index];
    if (!result || result.key !== lane.focusId) {
      throw new Error('runner result identity mismatch; inspect workflow receipts');
    }
    completed.push({
      focusId: lane.focusId, invocationId: lane.invocationId,
      packetDigest: args.packetDigest, ...result,
    });
  }
  // Emit settled evidence even when a failed child blocks subsequent waves.
  emit({ completed: completed.slice() });
  if (results.some(result => result.ok !== true)) {
    throw new Error('reviewer failed; stop, preserve receipts, and report the blocker without fallback');
  }
}
return completed;
