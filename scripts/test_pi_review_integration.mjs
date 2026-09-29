import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { parseReviewInvocation } from '../pi-config/skills/review-pipeline/command.mjs';
import { captureLocalEvidence, verifyLocalSnapshot } from '../pi-config/skills/review-pipeline/evidence.mjs';
import { buildReviewerLaunch } from '../pi-config/skills/review-pipeline/launch.mjs';
import { selectFocuses, validateReviewBundle } from '../pi-config/skills/review-pipeline/validate.mjs';

const skill = new URL('../pi-config/skills/review-pipeline/', import.meta.url);
const registry = JSON.parse(readFileSync(new URL('pipeline.json', skill)));
const schema = JSON.parse(readFileSync(new URL('report.schema.json', skill)));
test('every routed focus has a readable review lens, including general', () => {
  for (const focus of [...registry.focuses, registry.general]) {
    const path = new URL(focus.file, skill);
    assert.ok(existsSync(path), `Missing ${focus.id} lens at ${path}`);
    assert.ok(readFileSync(path, 'utf8').trim());
  }
});
const focusTexts = Object.fromEntries([...registry.focuses, registry.general]
  .filter(focus => existsSync(new URL(focus.file, skill)))
  .map(focus => [focus.id, readFileSync(new URL(focus.file, skill), 'utf8')]));
function git(repo, ...args) {
  const result = spawnSync('git', args, { cwd: repo, encoding: 'utf8', env: { ...process.env, GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: '/dev/null' } });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}
function repoFixture(t) {
  const dir = mkdtempSync(join(tmpdir(), 'pi-review-flow-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const repo = join(dir, 'repo');
  mkdirSync(repo);
  git(repo, 'init', '-q');
  git(repo, 'config', 'user.name', 'Test');
  git(repo, 'config', 'user.email', 'test@example.com');
  writeFileSync(join(repo, 'example.ts'), 'export const value = 1;\n');
  git(repo, 'add', '.'); git(repo, 'commit', '-qm', 'base');
  writeFileSync(join(repo, 'example.ts'), 'export const value = 2;\n');
  writeFileSync(join(repo, 'another.ts'), 'export const newValue = 3;\n');
  return { dir, repo };
}
function report(expected, packet) {
  return { focus_id: expected.focusId, invocation_id: expected.invocationId, packet_digest: packet.packet_digest,
    success: true, summary: 'Reviewed the frozen fixture.', coverage: {
      reviewed_file_ids: packet.changed_files.map(file => file.id), omitted_file_ids: [],
      reviewed_hunk_ids: packet.hunks.map(hunk => hunk.id), omitted_hunk_ids: [] },
    findings: [], findings_omitted: 0, strengths: [], errors: [] };
}

test('current parallel, single and named focus consume frozen evidence and preserve the reviewed checkout', async t => {
  const { dir, repo } = repoFixture(t);
  const before = git(repo, 'status', '--porcelain=v1');
  const packet = await captureLocalEvidence({ repo, scope: 'current' });
  assert.equal(packet.complete, true);
  assert.equal((await verifyLocalSnapshot(packet)).valid, true);
  const packetRef = join(dir, 'frozen.json');
  writeFileSync(packetRef, JSON.stringify(packet));
  const selected = selectFocuses(registry, packet.changed_files).selected;
  for (const [tokens, expectedKind, focus] of [[[], 'workflow', null], [['single'], 'direct', 'general'], [['simplify'], 'direct', 'simplicity']]) {
    const invocation = parseReviewInvocation(tokens, registry);
    const launch = buildReviewerLaunch({ invocation, selectedFocuses: selected, packetRef,
      packetDigest: packet.packet_digest, assignedIds: { files: packet.changed_files.map(f => f.id), hunks: packet.hunks.map(h => h.id) },
      focusTexts, schema, cwd: repo });
    assert.equal(launch.kind, expectedKind);
    if (focus) assert.deepEqual(launch.expected.map(row => row.focusId), [focus]);
    const results = launch.expected.map(row => ({ key: row.focusId, focusId: row.focusId, invocationId: row.invocationId,
      packetDigest: packet.packet_digest, runId: `run-${row.focusId}`, ok: true, structuredOutput: report(row, packet) }));
    const result = await validateReviewBundle({ packet, expected: launch.expected,
      configuredIdentity: { model: 'openai-codex/gpt-5.6-terra', thinking: 'medium' },
      runtimeIdentities: Object.fromEntries(results.map(row => [row.runId, { model: 'openai-codex/gpt-5.6-terra', thinking: 'medium' }])),
      results, evidenceDecisions: [] });
    assert.equal(result.verdict, 'Passes Review');
    assert.equal(result.coverage, 'complete');
    assert.equal(result.counts.selected, launch.expected.length);
    if (focus === 'simplicity') assert.ok(selected.some(row => row.id !== focus), 'Explicit focus is a filtered-scope pass only');
  }
  assert.equal(git(repo, 'status', '--porcelain=v1'), before, 'Review preparation must not edit the checkout');
});

test('failed parallel wave or missing reports cannot turn empty findings into a pass', async t => {
  const { dir, repo } = repoFixture(t);
  const packet = await captureLocalEvidence({ repo, scope: 'current' });
  const selected = selectFocuses(registry, packet.changed_files).selected;
  const launch = buildReviewerLaunch({ invocation: parseReviewInvocation([], registry), selectedFocuses: selected,
    packetRef: join(dir, 'evidence.json'), packetDigest: packet.packet_digest,
    assignedIds: { files: packet.changed_files.map(f => f.id), hunks: packet.hunks.map(h => h.id) }, focusTexts, schema, cwd: repo });
  const result = await validateReviewBundle({ packet, expected: launch.expected,
    configuredIdentity: { model: 'openai-codex/gpt-5.6-terra', thinking: 'medium' }, runtimeIdentities: {},
    results: [], evidenceDecisions: [] });
  assert.equal(result.verdict, 'Inconclusive');
  assert.equal(result.coverage, 'incomplete');
  assert.equal(result.counts.completed, 0);
});

test('explicit PR URL parses without taking local evidence; invalid invocation fails before launch', () => {
  const url = 'https://github.com/example/repo/pull/7';
  assert.deepEqual(parseReviewInvocation(['pr', url], registry), {
    mode: 'parallel', focusId: null, scope: 'pr', prUrl: url, legacySyntax: false });
  assert.throws(() => parseReviewInvocation(['pr'], registry), /invalid/i);
});
