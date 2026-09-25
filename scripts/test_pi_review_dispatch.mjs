import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { test } from 'node:test';

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

async function execute(args, response) {
  assert.ok(existsSync(recipe), 'Canonical dispatch recipe is not implemented');
  const batches = [];
  const events = [];
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
  for (const value of [0, 11, '2', 1.5]) {
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

test('preserves an absent structured report for inconclusive reconciliation', async () => {
  const { result } = await execute(input(), lanes => lanes.map(lane => ({
    key: lane.key, ok: true, runId: 'run', output: 'malformed JSON',
  })));
  assert.equal(result[0].structuredOutput, undefined);
  assert.equal(result[0].output, 'malformed JSON');
});
