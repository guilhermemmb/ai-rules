import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, chmodSync, symlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

const evidenceModule = new URL('../pi-config/skills/review-pipeline/evidence.mjs', import.meta.url);
async function api() {
  const { existsSync } = await import('node:fs');
  assert.ok(existsSync(evidenceModule), 'Local evidence collector is missing');
  return import(evidenceModule);
}
function git(repo, ...args) {
  const result = spawnSync('git', args, { cwd: repo, encoding: 'utf8', env: { ...process.env, GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: '/dev/null' } });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}
function fixture(t) {
  const repo = mkdtempSync(join(tmpdir(), 'pi-review-evidence-'));
  t.after(() => rmSync(repo, { recursive: true, force: true }));
  git(repo, 'init', '-q');
  git(repo, 'config', 'user.name', 'Test');
  git(repo, 'config', 'user.email', 'test@example.com');
  writeFileSync(join(repo, 'tracked.txt'), 'initial\n');
  git(repo, 'add', '.');
  git(repo, 'commit', '-qm', 'base');
  return repo;
}

test('current captures staged, worktree and untracked layers without double-counting final paths', async t => {
  const repo = fixture(t);
  writeFileSync(join(repo, 'tracked.txt'), 'staged\n');
  git(repo, 'add', 'tracked.txt');
  writeFileSync(join(repo, 'tracked.txt'), 'unstaged\n');
  writeFileSync(join(repo, 'new file.txt'), 'untracked\n');
  const { captureLocalEvidence, verifyLocalSnapshot } = await api();
  const packet = await captureLocalEvidence({ repo, scope: 'current' });
  assert.equal(packet.complete, true);
  assert.deepEqual(packet.layers.map(layer => layer.name), ['index', 'worktree', 'untracked']);
  assert.deepEqual(packet.changed_files.map(file => file.new_path).sort(), ['new file.txt', 'tracked.txt']);
  assert.equal(new Set(packet.changed_files.map(file => file.id)).size, 2);
  assert.ok(packet.hunks.filter(hunk => hunk.file_id === packet.changed_files.find(file => file.new_path === 'tracked.txt').id).length >= 2);
  assert.match(packet.full_diff_ref, /\+staged/);
  assert.match(packet.full_diff_ref, /\+unstaged/);
  assert.ok(packet.layers.every(layer => /^sha256:[a-f0-9]{64}$/.test(layer.sha256)));
  assert.match(packet.packet_digest, /^sha256:[a-f0-9]{64}$/);
  assert.equal((await verifyLocalSnapshot(packet)).valid, true);
  const repeat = await captureLocalEvidence({ repo, scope: 'current' });
  assert.deepEqual(packet.changed_files, repeat.changed_files);
  assert.deepEqual(packet.hunks, repeat.hunks);
  assert.equal(packet.packet_digest, repeat.packet_digest);
  writeFileSync(join(repo, 'new file.txt'), 'mutated\n');
  assert.equal((await verifyLocalSnapshot(packet)).valid, false);
});

test('narrow scopes exclude other layers and detect index mutation', async t => {
  const repo = fixture(t);
  writeFileSync(join(repo, 'tracked.txt'), 'staged\n');
  git(repo, 'add', 'tracked.txt');
  writeFileSync(join(repo, 'tracked.txt'), 'unstaged\n');
  writeFileSync(join(repo, 'extra.txt'), 'new\n');
  const { captureLocalEvidence, verifyLocalSnapshot } = await api();
  const staged = await captureLocalEvidence({ repo, scope: 'staged' });
  const unstaged = await captureLocalEvidence({ repo, scope: 'unstaged' });
  assert.deepEqual(staged.layers.map(layer => layer.name), ['index']);
  assert.deepEqual(unstaged.layers.map(layer => layer.name), ['worktree']);
  assert.doesNotMatch(staged.full_diff_ref, /extra.txt|unstaged/);
  assert.doesNotMatch(unstaged.full_diff_ref, /extra.txt|staged\\n/);
  writeFileSync(join(repo, 'tracked.txt'), 'index changed\n');
  git(repo, 'add', 'tracked.txt');
  assert.equal((await verifyLocalSnapshot(staged)).valid, false);
});

test('current preserves opposing staged and unstaged edits even when final bytes equal HEAD', async t => {
  const repo = fixture(t);
  writeFileSync(join(repo, 'tracked.txt'), 'temporary\n');
  git(repo, 'add', 'tracked.txt');
  writeFileSync(join(repo, 'tracked.txt'), 'initial\n');
  const { captureLocalEvidence } = await api();
  const packet = await captureLocalEvidence({ repo, scope: 'current' });
  assert.deepEqual(packet.changed_files.map(file => file.new_path), ['tracked.txt']);
  assert.equal(packet.hunks.length, 2);
});

test('renamed paths have one stable final file identity across index and worktree', async t => {
  const repo = fixture(t);
  git(repo, 'mv', 'tracked.txt', 'renamed.txt');
  writeFileSync(join(repo, 'renamed.txt'), 'renamed content\n');
  const { captureLocalEvidence } = await api();
  const packet = await captureLocalEvidence({ repo, scope: 'current' });
  assert.deepEqual(packet.changed_files.map(file => [file.old_path, file.new_path]), [['tracked.txt', 'renamed.txt']]);
  assert.ok(packet.hunks.every(hunk => hunk.file_id === packet.changed_files[0].id));
});

test('an empty untracked file is file-level evidence, not a fabricated added line', async t => {
  const repo = fixture(t);
  writeFileSync(join(repo, 'empty.txt'), '');
  const { captureLocalEvidence } = await api();
  const packet = await captureLocalEvidence({ repo, scope: 'current' });
  assert.deepEqual(packet.changed_files.map(file => file.new_path), ['empty.txt']);
  assert.deepEqual(packet.hunks, []);
  assert.equal(packet.complete, true);
});

test('untracked binary, oversized, symlink and unreadable data remain explicit limitations', async t => {
  const repo = fixture(t);
  writeFileSync(join(repo, 'binary.bin'), Buffer.from([0, 1, 2]));
  writeFileSync(join(repo, 'oversized.txt'), 'x'.repeat(1024));
  symlinkSync('/etc/passwd', join(repo, 'external-link'));
  writeFileSync(join(repo, 'unreadable.txt'), 'hidden');
  chmodSync(join(repo, 'unreadable.txt'), 0);
  const { captureLocalEvidence } = await api();
  const packet = await captureLocalEvidence({ repo, scope: 'current', maxUntrackedBytes: 128 });
  assert.equal(packet.complete, false);
  assert.equal(packet.changed_files.find(file => file.new_path === 'binary.bin')?.binary, true);
  assert.ok(packet.limitations.some(item => /oversized.txt/.test(item)));
  assert.ok(packet.limitations.some(item => /external-link/.test(item)));
  assert.ok(packet.limitations.some(item => /unreadable.txt/.test(item)));
});
