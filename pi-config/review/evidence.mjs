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
const prUrlPattern = /^https?:\/\/[^/]+\/([^/]+)\/([^/]+)\/(?:pull|merge_requests)\/(\d+)\/?(?:[?#].*)?$/i;
const executeCommand = async (command, args, options = {}) => exec(command, args, {
  ...options,
  encoding: 'utf8',
  maxBuffer: 32 * 1024 * 1024,
  env: { ...process.env, GIT_CONFIG_NOSYSTEM: '1', ...(options.env ?? {}) },
});
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

function inventoryFromDiff(names, diff) {
  const patches = splitPatches(diff);
  if (patches.length !== names.length) throw new Error('Diff and changed-path inventory disagree');
  const changedFiles = [];
  const hunks = [];
  for (const [index, row] of names.entries()) {
    const path = row.new_path ?? row.old_path;
    const identity = sha(Buffer.from(path)).slice(7, 23);
    const patch = patches[index] ?? '';
    const binary = /^Binary files |^GIT binary patch/m.test(patch);
    const file = { id: `f-${identity}`, old_path: row.old_path, new_path: row.new_path,
      status: row.status, binary };
    changedFiles.push(file);
    hunks.push(...extractHunks(patch, file.id, identity));
  }
  return { changedFiles, hunks };
}

function packetDigest(packet) {
  packet.packet_digest = sha(Buffer.from(JSON.stringify(packet)));
  return packet;
}

function validBranchTarget(target) {
  return typeof target === 'string' && /^[A-Za-z0-9][A-Za-z0-9._/-]*$/.test(target) &&
    !target.includes('..') && !target.endsWith('.lock');
}

async function resolveBranchTarget(repo) {
  for (const candidate of ['@{upstream}', 'refs/remotes/origin/HEAD']) {
    try {
      await git(repo, 'rev-parse', '--verify', `${candidate}^{commit}`);
      return candidate;
    } catch { /* try the next repository-owned candidate */ }
  }
  throw new Error('Cannot resolve branch comparison base from repository metadata');
}

async function branchIdentity(repo, target) {
  const [targetSha, baseSha, headSha] = await Promise.all([
    git(repo, 'rev-parse', '--verify', `${target}^{commit}`),
    git(repo, 'merge-base', target, 'HEAD'),
    git(repo, 'rev-parse', 'HEAD'),
  ]);
  return {
    targetSha: targetSha.toString().trim(),
    baseSha: baseSha.toString().trim(),
    headSha: headSha.toString().trim(),
  };
}

export async function captureBranchEvidence({ repo, target } = {}) {
  const cwd = await realpath(repo);
  const baseRef = target ?? await resolveBranchTarget(cwd);
  if (target !== undefined && !validBranchTarget(target)) throw new Error('Invalid branch comparison target');
  const identity = await branchIdentity(cwd, baseRef);
  const range = `${identity.baseSha}...${identity.headSha}`;
  const diffBytes = await git(cwd, 'diff', ...diffFlags, range);
  const names = parseNames(await git(cwd, 'diff', '--name-status', '-z', '--find-renames', range));
  const diff = diffBytes.toString('utf8');
  const { changedFiles, hunks } = inventoryFromDiff(names, diff);
  const repeated = await branchIdentity(cwd, baseRef);
  if (JSON.stringify(identity) !== JSON.stringify(repeated)) throw new Error('Branch refs mutated during evidence capture');
  const layer = { name: 'branch', sha256: sha(diffBytes), paths: names.map((row) => row.new_path ?? row.old_path) };
  const framework_context = await collectFrameworkContext({
    repoRoot: cwd,
    changedFiles,
    layers: [layer],
    readAt: async (path) => {
      try {
        const bytes = await git(cwd, 'show', `${identity.headSha}:${path}`);
        return { bytes, ref: `${identity.headSha}:${path}` };
      } catch { return null; }
    },
  });
  const limitations = [...framework_context.limitations];
  return packetDigest({
    scope: 'branch',
    scope_detail: { target: baseRef, target_sha: identity.targetSha },
    filter: null,
    repo: cwd,
    cwd,
    base_ref: baseRef,
    base_sha: identity.baseSha,
    head_sha: identity.headSha,
    snapshot_id: sha(Buffer.from(JSON.stringify({ baseRef, ...identity }))),
    diff_sha256: sha(diffBytes),
    layers: [layer],
    changed_files: changedFiles,
    hunks,
    framework_context,
    full_diff_ref: diff,
    complete: limitations.length === 0,
    limitations,
  });
}

export async function verifyBranchSnapshot(packet) {
  if (!packet || packet.scope !== 'branch' || !packet.repo || !packet.base_ref) {
    return { valid: false, reason: 'Invalid branch packet' };
  }
  try {
    const identity = await branchIdentity(packet.repo, packet.base_ref);
    const valid = identity.targetSha === packet.scope_detail?.target_sha &&
      identity.baseSha === packet.base_sha && identity.headSha === packet.head_sha;
    return valid ? { valid: true } : { valid: false, reason: 'Branch base/head identity changed' };
  } catch (error) {
    return { valid: false, reason: `Cannot recheck branch identity: ${error.message}` };
  }
}

function prFileInventory(files, diff) {
  const patches = splitPatches(diff);
  if (patches.length !== files.length) throw new Error('PR diff and changed-path inventory disagree');
  const names = files.map((file) => ({
    status: file.previousFilename ? 'R' : 'M',
    old_path: file.previousFilename ?? file.path,
    new_path: file.path,
  }));
  return inventoryFromDiff(names, diff);
}

async function prMetadata(url, repo, execute) {
  const result = await execute('gh', ['pr', 'view', url, '--json',
    'files,title,body,url,baseRefName,baseRefOid,headRefName,headRefOid'], { cwd: repo });
  return JSON.parse(String(result.stdout));
}

export async function capturePrEvidence({ repo, url, execute = executeCommand } = {}) {
  const match = typeof url === 'string' && url.match(prUrlPattern);
  if (!match) throw new Error('Invalid PR URL');
  const before = await prMetadata(url, repo, execute);
  const diffResult = await execute('gh', ['pr', 'diff', url, '--patch'], { cwd: repo });
  const diff = String(diffResult.stdout);
  const after = await prMetadata(url, repo, execute);
  if (before.baseRefOid !== after.baseRefOid || before.headRefOid !== after.headRefOid) {
    throw new Error('PR refs mutated during evidence capture');
  }
  if (!/^[a-f0-9]{40}$/i.test(before.baseRefOid) || !/^[a-f0-9]{40}$/i.test(before.headRefOid)) {
    throw new Error('PR metadata is missing immutable base/head identities');
  }
  const files = Array.isArray(before.files) ? before.files : [];
  const { changedFiles, hunks } = prFileInventory(files, diff);
  const [owner, repository] = [match[1], match[2].replace(/\.git$/i, '')];
  const layer = { name: 'pr', sha256: sha(Buffer.from(diff)), paths: changedFiles.map((file) => file.new_path ?? file.old_path) };
  const framework_context = await collectFrameworkContext({
    repoRoot: repo,
    changedFiles,
    layers: [layer],
    readAt: async (path) => {
      try {
        const response = await execute('gh', ['api', '--method', 'GET',
          `repos/${owner}/${repository}/contents/${path}?ref=${before.headRefOid}`], { cwd: repo });
        const payload = JSON.parse(String(response.stdout));
        if (payload.encoding !== 'base64' || typeof payload.content !== 'string') return null;
        return { bytes: Buffer.from(payload.content.replace(/\s/g, ''), 'base64'),
          ref: `${before.headRefOid}:${path}` };
      } catch { return null; }
    },
  });
  const limitations = [...framework_context.limitations];
  return packetDigest({
    scope: 'pr',
    scope_detail: {
      url: before.url ?? url,
      title: before.title ?? '',
      body: before.body ?? '',
      base_ref: before.baseRefName ?? null,
      head_ref: before.headRefName ?? null,
    },
    filter: null,
    repo,
    cwd: repo,
    base_ref: before.baseRefName ?? null,
    base_sha: before.baseRefOid,
    head_sha: before.headRefOid,
    snapshot_id: sha(Buffer.from(JSON.stringify({ url, base: before.baseRefOid, head: before.headRefOid }))),
    diff_sha256: sha(Buffer.from(diff)),
    layers: [layer],
    changed_files: changedFiles,
    hunks,
    framework_context,
    full_diff_ref: diff,
    complete: limitations.length === 0,
    limitations,
  });
}

export async function verifyPrSnapshot(packet, { execute = executeCommand } = {}) {
  if (!packet || packet.scope !== 'pr' || !packet.scope_detail?.url) {
    return { valid: false, reason: 'Invalid PR packet' };
  }
  try {
    const metadata = await prMetadata(packet.scope_detail.url, packet.repo, execute);
    const valid = metadata.baseRefOid === packet.base_sha && metadata.headRefOid === packet.head_sha;
    return valid ? { valid: true } : { valid: false, reason: 'PR base/head identity changed' };
  } catch (error) {
    return { valid: false, reason: `Cannot recheck PR identity: ${error.message}` };
  }
}

export async function verifyEvidenceSnapshot(packet, options) {
  if (packet?.scope === 'pr') return verifyPrSnapshot(packet, options);
  if (packet?.scope === 'branch') return verifyBranchSnapshot(packet);
  return verifyLocalSnapshot(packet);
}
