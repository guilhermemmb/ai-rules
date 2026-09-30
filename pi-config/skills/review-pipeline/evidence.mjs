import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { lstat, open, readFile, realpath } from 'node:fs/promises';
import { promisify } from 'node:util';
import { resolve, relative, sep } from 'node:path';
import { collectFrameworkContext } from './framework.mjs';

const exec = promisify(execFile);
const sha = bytes => `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
const git = async (repo, ...args) => (await exec('git', ['-c', 'core.quotePath=false', ...args], {
  cwd: repo, encoding: 'buffer', maxBuffer: 32 * 1024 * 1024,
  env: { ...process.env, GIT_CONFIG_NOSYSTEM: '1' },
})).stdout;
const diffFlags = ['--no-ext-diff', '--no-textconv', '--no-color', '--binary', '--find-renames'];
const parseNames = bytes => {
  const parts = bytes.toString('utf8').split('\0').filter(Boolean);
  const entries = [];
  for (let index = 0; index < parts.length;) {
    const status = parts[index++];
    const renamed = /^[RC]/.test(status);
    const first = parts[index++];
    if (!first) throw new Error('Incomplete NUL-delimited Git status');
    entries.push({ status: status[0], old_path: renamed ? first : status[0] === 'A' ? null : first,
      new_path: status[0] === 'D' ? null : renamed ? parts[index++] : first });
  }
  return entries;
};
const extractHunks = (diff, fileId, prefix, offset = 0) => [...diff.matchAll(/^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@/gm)]
  .map((match, index) => ({ id: `h-${prefix}-${offset + index + 1}`, file_id: fileId,
    old_start: Number(match[1]), old_count: Number(match[2] ?? 1),
    new_start: Number(match[3]), new_count: Number(match[4] ?? 1), content_ref: 'full_diff_ref' }));
const splitPatches = diff => diff.split(/(?=^diff --git )/m).filter(part => part.startsWith('diff --git '));

async function untrackedFile(repo, root, path, maxBytes) {
  const absolute = resolve(repo, path);
  const outside = absolute !== root && !absolute.startsWith(`${root}${sep}`);
  if (outside) return { limitation: `${path}: escapes repository`, binary: true, patch: '' };
  try {
    const info = await lstat(absolute);
    if (!info.isFile() || !(info.mode & 0o444)) return { limitation: `${path}: unreadable or non-regular file`, binary: true, patch: '' };
    const target = await realpath(absolute);
    if (target !== root && !target.startsWith(`${root}${sep}`)) return { limitation: `${path}: symlink escapes repository`, binary: true, patch: '' };
    if (info.size > maxBytes) return { limitation: `${path}: exceeds ${maxBytes} byte limit`, binary: true, patch: '' };
    const handle = await open(absolute, constants.O_RDONLY | constants.O_NOFOLLOW);
    let data;
    try {
      if (!(await handle.stat()).isFile()) throw new Error('not a regular file');
      data = await handle.readFile();
    } finally { await handle.close(); }
    if (data.length > maxBytes) return { limitation: `${path}: exceeds ${maxBytes} byte limit`, binary: true, patch: '' };
    const binary = data.includes(0);
    const header = `diff --git a/${path} b/${path}\nnew file mode 100644\n--- /dev/null\n+++ b/${path}\n`;
    if (binary) return { binary, patch: `${header}Binary file ${path} (${data.length} bytes, sha256 ${sha(data)})\n` };
    if (data.length === 0) return { binary: false, patch: header };
    const lines = data.toString('utf8').replace(/\n$/, '').split('\n');
    const patch = `${header}@@ -0,0 +1,${lines.length} @@\n${lines.map(line => `+${line}`).join('\n')}\n`;
    return { binary, patch };
  } catch (error) {
    return { limitation: `${path}: cannot read (${error.code ?? error.message})`, binary: true, patch: '' };
  }
}

async function captureRaw(repo, scope, maxUntrackedBytes) {
  const head = (await git(repo, 'rev-parse', 'HEAD')).toString().trim();
  const index = await git(repo, 'diff', ...diffFlags, '--cached', 'HEAD');
  const indexNames = parseNames(await git(repo, 'diff', '--name-status', '-z', '--cached', '--find-renames', 'HEAD'));
  const worktree = await git(repo, 'diff', ...diffFlags);
  const untrackedNames = (await git(repo, 'ls-files', '--others', '--exclude-standard', '-z')).toString('utf8').split('\0').filter(Boolean).sort();
  const root = await realpath(repo);
  const untracked = [];
  for (const path of untrackedNames) untracked.push({ path, ...await untrackedFile(repo, root, path, maxUntrackedBytes) });
  const layers = [];
  if (scope !== 'unstaged') layers.push({ name: 'index', sha256: sha(index), paths: indexNames.map(row => row.new_path ?? row.old_path) });
  if (scope !== 'staged') layers.push({ name: 'worktree', sha256: sha(worktree), paths: parseNames(await git(repo, 'diff', '--name-status', '-z')).map(row => row.new_path ?? row.old_path) });
  if (scope === 'current') layers.push({ name: 'untracked', sha256: sha(Buffer.from(JSON.stringify(untracked))), paths: untrackedNames });
  return { head, index, indexNames, worktree, untracked, layers };
}

export async function captureLocalEvidence({ repo, scope, maxUntrackedBytes = 1024 * 1024 }) {
  if (!['current', 'staged', 'unstaged'].includes(scope) || !Number.isSafeInteger(maxUntrackedBytes) || maxUntrackedBytes < 1) {
    throw new Error('Invalid local review scope or untracked size limit');
  }
  const cwd = await realpath(repo);
  const raw = await captureRaw(cwd, scope, maxUntrackedBytes);
  const snapshotId = sha(Buffer.from(JSON.stringify({ head: raw.head, layers: raw.layers })));
  const comparison = await captureRaw(cwd, scope, maxUntrackedBytes);
  if (snapshotId !== sha(Buffer.from(JSON.stringify({ head: comparison.head, layers: comparison.layers })))) {
    throw new Error('Local changes mutated during evidence capture');
  }
  const worktreeNames = scope !== 'staged'
    ? parseNames(await git(cwd, 'diff', '--name-status', '-z', '--find-renames')) : [];
  const sources = scope === 'staged' ? [{ names: raw.indexNames, diff: raw.index }]
    : scope === 'unstaged' ? [{ names: worktreeNames, diff: raw.worktree }]
      : [{ names: raw.indexNames, diff: raw.index }, { names: worktreeNames, diff: raw.worktree }];
  const changed = new Map();
  const hunks = [];
  const limitations = [];
  const patches = [];
  for (const source of sources) {
    const patchBlocks = splitPatches(source.diff.toString('utf8'));
    if (patchBlocks.length !== source.names.length) throw new Error('Diff and changed-path inventory disagree');
    for (const [index, row] of source.names.entries()) {
      const stagedRename = raw.indexNames.find(item => item.status === 'R' &&
        (item.new_path === row.new_path || item.old_path === row.old_path));
      const path = stagedRename?.new_path ?? row.new_path ?? row.old_path;
      const identity = sha(Buffer.from(path)).slice(7, 23);
      const binary = /^Binary files |^GIT binary patch/m.test(patchBlocks[index] ?? '');
      const file = changed.get(path) ?? { id: `f-${identity}`, old_path: stagedRename?.old_path ?? row.old_path,
        new_path: stagedRename?.new_path ?? row.new_path, status: stagedRename ? 'R' : row.status, binary };
      file.binary ||= binary;
      changed.set(path, file);
      const prior = hunks.filter(hunk => hunk.file_id === file.id).length;
      hunks.push(...extractHunks(patchBlocks[index], file.id, identity, prior));
      patches.push(patchBlocks[index]);
    }
  }
  if (scope === 'current') for (const item of raw.untracked) {
    if (changed.has(item.path)) throw new Error(`Duplicate final path: ${item.path}`);
    const identity = sha(Buffer.from(item.path)).slice(7, 23);
    const file = { id: `f-${identity}`, old_path: null, new_path: item.path, status: 'A', binary: item.binary };
    changed.set(item.path, file);
    patches.push(item.patch);
    hunks.push(...extractHunks(item.patch, file.id, identity));
    if (item.limitation) limitations.push(item.limitation);
    else if (item.binary) limitations.push(`${item.path}: binary content unavailable for text review`);
  }
  if (scope !== 'current' && raw.untracked.length) limitations.push('Untracked files excluded by explicit narrow scope');
  const frameworkLayer = { name: scope === 'staged' ? 'index' : 'worktree' };
  const framework_context = await collectFrameworkContext({ repoRoot: cwd, changedFiles: [...changed.values()], layers: [frameworkLayer],
    readAt: async path => {
      try {
        const bytes = scope === 'staged' ? await git(cwd, 'show', `:${path}`) : await readFile(resolve(cwd, path));
        return { bytes, ref: scope === 'staged' ? `index:${path}` : `worktree:${path}` };
      } catch { return null; }
    },
  });
  limitations.push(...framework_context.limitations);
  const fullDiff = patches.join('');
  const packet = { scope, scope_detail: null, filter: null, repo: cwd, cwd, base_ref: 'HEAD', base_sha: raw.head,
    head_sha: raw.head, snapshot_id: snapshotId, diff_sha256: sha(Buffer.from(fullDiff)),
    layers: raw.layers, changed_files: [...changed.values()], hunks, framework_context, full_diff_ref: fullDiff,
    complete: limitations.length === 0, limitations, max_untracked_bytes: maxUntrackedBytes };
  // The digest is over precisely these serialized bytes, before adding packet_digest.
  packet.packet_digest = sha(Buffer.from(JSON.stringify(packet)));
  if (!(await verifyLocalSnapshot(packet)).valid) throw new Error('Local changes mutated during packet assembly');
  return packet;
}

export async function verifyLocalSnapshot(packet) {
  if (!packet || !['current', 'staged', 'unstaged'].includes(packet.scope) || !packet.repo) return { valid: false, reason: 'Invalid local packet' };
  try {
    const current = await captureRaw(packet.repo, packet.scope, packet.max_untracked_bytes ?? 1024 * 1024);
    const actual = sha(Buffer.from(JSON.stringify({ head: current.head, layers: current.layers })));
    return actual === packet.snapshot_id ? { valid: true } : { valid: false, reason: 'Local HEAD/index/worktree/untracked snapshot changed' };
  } catch (error) {
    return { valid: false, reason: `Cannot recheck local snapshot: ${error.message}` };
  }
}
