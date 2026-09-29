import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { test } from 'node:test';
import { homedir } from 'node:os';
import { pathToFileURL } from 'node:url';

const recipe = new URL('../pi-config/skills/review-pipeline/dispatch.js', import.meta.url);
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

function input() {
  return {
    maxConcurrency: 2,
    packetDigest: 'sha256:fixture',
    reportSchema: { type: 'object', required: ['findings'] },
    lanes: [
      { focusId: 'correctness', invocationId: 'one', task: 'Review correctness.' },
      { focusId: 'security', invocationId: 'two', task: 'Review security.' },
      { focusId: 'git-safety', invocationId: 'three', task: 'Review diff safety.' },
    ],
  };
}

async function execute(args, response, events = []) {
  assert.ok(existsSync(recipe), 'Canonical dispatch recipe is not implemented');
  const batches = [];
  const runs = { all: async (lanes) => {
    batches.push(lanes);
    return response ? response(lanes) : lanes.map(lane => ({
      key: lane.key, ok: true, runId: `run-${lane.key}`,
      structuredOutput: { findings: [] }, output: 'raw report',
      outputReference: { path: `/artifacts/${lane.key}` },
    }));
  } };
  const run = new AsyncFunction('args', 'runs', 'emit', readFileSync(recipe, 'utf8'));
  const result = await run(args, runs, event => events.push(event));
  return { result, batches, events };
}

test('dispatches bounded fresh reviewer lanes without overriding agent policy', async () => {
  const { result, batches } = await execute(input());
  assert.deepEqual(batches.map(batch => batch.length), [2, 1]);
  assert.equal(result.length, 3);
  for (const lane of batches.flat()) {
    assert.equal(lane.agent, 'reviewer');
    assert.equal(lane.context, 'fresh');
    for (const field of ['model', 'thinking', 'tools', 'extensions', 'config']) {
      assert.equal(Object.hasOwn(lane, field), false, `${field} belongs to agent policy`);
    }
    assert.deepEqual(lane.outputSchema, input().reportSchema);
  }
  assert.deepEqual(result.map(row => [row.focusId, row.invocationId, row.runId]), [
    ['correctness', 'one', 'run-correctness'],
    ['security', 'two', 'run-security'],
    ['git-safety', 'three', 'run-git-safety'],
  ]);
  assert.equal(result[0].outputReference.path, '/artifacts/correctness');
});

test('rejects absent lanes before trying map or dispatch', async () => {
  await assert.rejects(execute({ ...input(), lanes: undefined }), /lanes must be a non-empty array/);
});

test('rejects duplicate focus or invocation identities', async () => {
  for (const field of ['focusId', 'invocationId']) {
    const args = input();
    args.lanes[1][field] = args.lanes[0][field];
    await assert.rejects(execute(args), /duplicate/);
  }
});

test('rejects invalid concurrency rather than silently broadening fanout', async () => {
  for (const value of [0, 5, 10, 11, '2', 1.5]) {
    await assert.rejects(execute({ ...input(), maxConcurrency: value }), /maxConcurrency/);
  }
});

test('rejects empty tasks and absent schema or evidence identity', async () => {
  const badTask = input();
  badTask.lanes[0].task = '';
  await assert.rejects(execute(badTask), /task/);
  await assert.rejects(execute({ ...input(), reportSchema: null }), /reportSchema/);
  await assert.rejects(execute({ ...input(), packetDigest: '' }), /packetDigest/);
});

test('does not treat a failed child as successful or dispatch further waves', async () => {
  let batches = 0;
  await assert.rejects(execute(input(), lanes => {
    batches++;
    return lanes.map(lane => ({ key: lane.key, ok: false, runId: 'failed-run', error: 'quota' }));
  }), /failed/);
  assert.equal(batches, 1);
});

test('rejects missing or reordered runner results instead of misattributing a focus', async () => {
  await assert.rejects(execute(input(), () => undefined), /results/);
  await assert.rejects(execute(input(), () => []), /results/);
  await assert.rejects(execute(input(), lanes => lanes.map(lane => ({ key: lane.key, ok: true })).reverse()), /identity/);
});

test('runs eight focuses in two settled waves of four using registry concurrency', async () => {
  const registry = JSON.parse(readFileSync(new URL('../pi-config/skills/review-pipeline/pipeline.json', import.meta.url)));
  const args = { ...input(), maxConcurrency: registry.max_concurrent_reviewers,
    lanes: Array.from({ length: 8 }, (_, i) => ({ focusId: `focus-${i}`, invocationId: `inv-${i}`, task: 'Review.' })) };
  let release;
  let firstWaveStarted;
  const started = new Promise(resolve => { firstWaveStarted = resolve; });
  const firstWave = new Promise(resolve => { release = resolve; });
  const sizes = [];
  const pending = execute(args, lanes => {
    sizes.push(lanes.length);
    const results = lanes.map(lane => ({ key: lane.key, ok: true, structuredOutput: { findings: [] } }));
    if (sizes.length === 1) {
      firstWaveStarted();
      return firstWave.then(() => results);
    }
    return results;
  });
  await started;
  const beforeRelease = sizes.slice();
  release();
  const { result } = await pending;
  assert.deepEqual(beforeRelease, [4]);
  assert.deepEqual(sizes, [4, 4]);
  assert.equal(result.length, 8);
});

test('binds inline structured reports independently of inherited file-only defaults', async () => {
  const { result, batches } = await execute(input());
  for (const lane of batches.flat()) {
    assert.equal(lane.outputMode, 'inline');
    assert.equal(lane.output, false, 'Do not inherit aggregate-derived mandatory child files');
    assert.equal(lane.artifacts, true, 'Runtime retains diagnostic files');
    assert.deepEqual(lane.acceptance, { level: 'attested', report: 'on' });
  }
  assert.deepEqual(result[0].structuredOutput, { findings: [] });
});

test('emits compact progress without repeatedly copying full reports', async () => {
  const { events, result } = await execute(input());
  assert.equal(events.length, 2);
  assert.deepEqual(events.map(event => [event.settled, event.total]), [[2, 3], [3, 3]]);
  assert.deepEqual(events[0].lanes.map(lane => lane.focusId), ['correctness', 'security']);
  assert.equal(events[0].lanes[0].runId, 'run-correctness');
  assert.equal(events[0].lanes[0].outputReference.path, '/artifacts/correctness');
  assert.equal(JSON.stringify(events).includes('raw report'), false);
  assert.equal(JSON.stringify(events).includes('structuredOutput'), false);
  assert.deepEqual(result[0].structuredOutput, { findings: [] });
});

test('retains full partial reports and errors before stopping subsequent waves', async () => {
  const events = [];
  await assert.rejects(execute(input(), lanes => lanes.map((lane, i) => ({
    key: lane.key, ok: i === 0, runId: `run-${lane.key}`,
    structuredOutput: { findings: ['partial evidence'] },
    ...(i === 0 ? {} : { error: 'provider failed' }),
    artifactPaths: { meta: `/logs/${lane.key}.json` },
  })), events), /failed/);
  const partial = events.at(-1).completed;
  assert.equal(partial.length, 2);
  assert.deepEqual(partial[0].structuredOutput.findings, ['partial evidence']);
  assert.equal(partial[1].error, 'provider failed');
  assert.equal(partial[1].artifactPaths.meta, '/logs/security.json');
});

// Characterize the installed runtime boundary that caused the original failure.
// CI without Pi runs the portable fixtures above; local verification must run this too.
const runtimeRoot = process.env.PI_SUBAGENTS_ROOT || `${homedir()}/.pi/agent/npm/node_modules/pi-subagents`;
test('installed runtime keeps acceptanceReport beside the strict review value', {
  skip: !existsSync(`${runtimeRoot}/src/runs/shared/structured-output.js`),
}, async () => {
  const runtime = await import(pathToFileURL(`${runtimeRoot}/src/runs/shared/structured-output.js`).href);
  const acceptance = await import(pathToFileURL(`${runtimeRoot}/src/runs/shared/acceptance.js`).href);
  const schema = JSON.parse(readFileSync(new URL('../pi-config/skills/review-pipeline/report.schema.json', import.meta.url)));
  const { batches } = await execute({ ...input(), reportSchema: schema });
  const lane = batches[0][0];
  const mode = acceptance.resolveAcceptanceReportMode(lane.acceptance);
  assert.equal(mode, 'required');
  const parameters = runtime.createStructuredOutputToolParameters(lane.outputSchema, { acceptanceReport: mode });
  const value = {
    focus_id: 'correctness', invocation_id: 'one', packet_digest: `sha256:${'a'.repeat(64)}`,
    success: true, summary: 'Reviewed fixture.',
    coverage: { reviewed_file_ids: [], omitted_file_ids: [], reviewed_hunk_ids: [], omitted_hunk_ids: [] },
    findings: [], findings_omitted: 0, strengths: [], errors: [],
  };
  const acceptanceReport = {
    criteriaSatisfied: [{ id: 'criterion-1', status: 'satisfied', evidence: 'Reviewed the supplied fixture.' }],
    manualNotes: 'Read-only fixture review.', residualRisks: ['No live provider run.'],
  };
  assert.deepEqual(acceptance.validateAcceptanceReport(acceptanceReport).errors, []);
  assert.equal((await runtime.validateStructuredOutputValue(parameters, { value, acceptanceReport })).status, 'valid');
  assert.equal((await runtime.validateStructuredOutputValue(parameters, { value })).status, 'invalid');
  assert.equal((await runtime.validateStructuredOutputValue(schema, { ...value, acceptanceReport: {} })).status, 'invalid');
});

test('preserves an absent structured report for inconclusive reconciliation', async () => {
  const { result } = await execute(input(), lanes => lanes.map(lane => ({
    key: lane.key, ok: true, runId: 'run', output: 'malformed JSON',
  })));
  assert.equal(result[0].structuredOutput, undefined);
  assert.equal(result[0].output, 'malformed JSON');
});
