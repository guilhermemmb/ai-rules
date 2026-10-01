import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { lstat, mkdir, open, readFile, realpath } from 'node:fs/promises';
import { homedir } from 'node:os';
import { isAbsolute, join, resolve, sep } from 'node:path';
import {
  captureBranchEvidence,
  captureLocalEvidence,
  capturePrEvidence,
  verifyEvidenceSnapshot,
} from './evidence.mjs';
import { loadPinnedReactRules } from './react-rules.mjs';

const SCOPES = new Set(['current', 'branch', 'staged', 'unstaged', 'pr']);
const MODES = new Set(['parallel', 'single']);
const CONTROL = /[\u0000-\u001f\u007f]/;
const REVIEWER_MODEL = 'openai-codex/gpt-5.6-terra';
const REVIEWER_THINKING = 'medium';
const sha = (value) => `sha256:${createHash('sha256').update(value).digest('hex')}`;
const USAGE = 'Usage: /review [parallel|single|<focus>] [current|branch|staged|unstaged|pr <url>]';

const CODE_EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.py', '.pyi', '.go', '.rs', '.java', '.kt', '.rb', '.php', '.c', '.h', '.cpp', '.cs', '.swift', '.sh', '.sql', '.html', '.css', '.scss', '.vue', '.svelte'];
export const REVIEW_FOCUSES = Object.freeze([
  { id: 'correctness', label: 'Correctness', aliases: [], triggers: { any_of: [
    { path_patterns: ['**/*.json', '**/*.jsonc', '**/*.yaml', '**/*.yml', '**/*.toml', '**/*.ini', '**/*.conf', '**/*.config', '**/Dockerfile*', '**/.env*', '**/.npmrc', '**/.yarnrc*', '**/*.tf', '**/*.xml', '**/*.gradle', '**/*.gradle.kts', '**/go.mod', '**/requirements*.txt', '**/Pipfile', '**/Gemfile'] },
    { path_patterns: ['**'], extensions: CODE_EXTENSIONS },
  ] } },
  { id: 'simplicity', label: 'Simplicity', aliases: ['simplify'], triggers: { any_of: [
    { path_patterns: ['**'], extensions: CODE_EXTENSIONS },
  ] } },
  { id: 'accessibility', label: 'Accessibility (a11y)', aliases: [], triggers: { any_of: [
    { path_patterns: ['**'], extensions: ['.tsx', '.jsx', '.html', '.vue', '.svelte', '.css', '.scss'] },
    { path_patterns: ['**/hooks/**', '**/*Focus*', '**/*focus*', '**/*Keyboard*', '**/*keyboard*', '**/*A11y*', '**/*a11y*', '**/*Accessibility*', '**/*accessibility*', '**/*ReducedMotion*', '**/*reducedMotion*', '**/*reduced-motion*'], extensions: ['.ts', '.js', '.mts', '.mjs', '.cts', '.cjs'] },
  ] } },
  { id: 'security', label: 'Security', aliases: [], triggers: { any_of: [
    { path_patterns: ['**'], extensions: CODE_EXTENSIONS },
    { path_patterns: ['**/*.json', '**/*.jsonc', '**/*.yaml', '**/*.yml', '**/*.toml', '**/*.ini', '**/*.conf', '**/*.config', '**/*.lock', '**/requirements*.txt', '**/Pipfile', '**/Gemfile', '**/Gemfile.lock', '**/go.mod', '**/go.sum', '**/Dockerfile*', '**/.env*', '**/.npmrc', '**/.yarnrc*', '**/yarn.lock', '**/*.tf', '**/*.xml', '**/*.gradle', '**/*.gradle.kts'] },
  ] } },
  { id: 'performance', label: 'Performance', aliases: ['react-best-practices', 'react'], triggers: { any_of: [
    { path_patterns: ['**'], extensions: CODE_EXTENSIONS.filter((extension) => extension !== '.sh') },
  ] } },
  { id: 'maintainability', label: 'Maintainability', aliases: [], triggers: { any_of: [
    { path_patterns: ['**'], extensions: CODE_EXTENSIONS },
  ] } },
  { id: 'design-consistency', label: 'Design Consistency', aliases: [], triggers: { any_of: [
    { path_patterns: ['**/components/**', '**/ui/**', '**/styles/**', '**/theme/**', '**/tokens/**', '**/pages/**', '**/views/**'], extensions: ['.ts', '.tsx', '.jsx', '.html', '.css', '.scss', '.vue', '.svelte'] },
  ] } },
  { id: 'git-safety', label: 'Git Safety', aliases: [], triggers: { always: true } },
]);

function catalogFrom(registry = { focuses: REVIEW_FOCUSES }) {
  const focuses = Array.isArray(registry) ? registry : registry?.focuses;
  if (!Array.isArray(focuses)) throw new Error(`Invalid focus registry. ${USAGE}`);
  const catalog = new Map();
  const ids = new Set();
  for (const focus of focuses) {
    const id = focus?.id?.toLowerCase();
    if (!id || ids.has(id) || SCOPES.has(id) || MODES.has(id) || id === 'general') {
      throw new Error(`Duplicate or colliding focus ID: ${focus?.id}. ${USAGE}`);
    }
    ids.add(id);
    for (const name of [focus.id, ...(focus.aliases ?? [])]) {
      const key = name?.toLowerCase();
      if (!key || catalog.has(key) || SCOPES.has(key) || MODES.has(key) || key === 'general') {
        throw new Error(`Ambiguous or colliding focus alias: ${name}. ${USAGE}`);
      }
      catalog.set(key, { id, reactOverlayRequested: id === 'performance' && key !== 'performance' });
    }
  }
  return catalog;
}

export function parseReviewInvocation(tokens, registry = { focuses: REVIEW_FOCUSES }) {
  const catalog = catalogFrom(registry);
  if (!Array.isArray(tokens) || tokens.some((token) => typeof token !== 'string' || CONTROL.test(token))) {
    throw new Error(`Invalid control character or token. ${USAGE}`);
  }
  const words = tokens.map((token) => token.toLowerCase());
  let mode = 'parallel';
  let focusId = null;
  let scope = 'current';
  let prUrl = null;
  let legacySyntax = false;
  let reactOverlayRequested = false;
  let index = 0;
  if (MODES.has(words[index])) mode = words[index++];
  else if (catalog.has(words[index])) {
    mode = 'focus';
    const focus = catalog.get(words[index++]);
    focusId = focus.id;
    reactOverlayRequested = focus.reactOverlayRequested;
  } else if (SCOPES.has(words[index])) {
    scope = words[index++];
  } else if (words.length) throw new Error(USAGE);

  if (SCOPES.has(words[index])) scope = words[index++];
  if (scope === 'pr') {
    const url = tokens[index++];
    if (!url || !/^https?:\/\/[^/]+\/[^/]+\/[^/]+\/(?:pull|merge_requests)\/\d+\/?(?:[?#].*)?$/i.test(url)) {
      throw new Error(`Invalid PR URL. ${USAGE}`);
    }
    prUrl = url;
  }
  if (SCOPES.has(words[0]) && catalog.has(words[index])) {
    mode = 'focus';
    const focus = catalog.get(words[index++]);
    focusId = focus.id;
    reactOverlayRequested = focus.reactOverlayRequested;
    legacySyntax = true;
  }
  if (index !== words.length) throw new Error(USAGE);
  return { mode, focusId, scope, prUrl, legacySyntax, reactOverlayRequested };
}

export function parseReviewText(input, registry = { focuses: REVIEW_FOCUSES }) {
  if (typeof input !== 'string' || CONTROL.test(input)) throw new Error(`Invalid control character. ${USAGE}`);
  const trimmed = input.trim();
  return parseReviewInvocation(trimmed ? trimmed.split(/ +/) : [], registry);
}

function glob(pattern, path) {
  let source = '^';
  for (let index = 0; index < pattern.length; index++) {
    if (pattern.slice(index, index + 3) === '**/') { source += '(?:.*/)?'; index += 2; }
    else if (pattern.slice(index, index + 2) === '**') { source += '.*'; index++; }
    else if (pattern[index] === '*') source += '[^/]*';
    else source += pattern[index].replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }
  return new RegExp(`${source}$`).test(path.replaceAll('\\', '/'));
}

function automaticSelection(packet) {
  const files = packet.changed_files;
  return REVIEW_FOCUSES.flatMap((focus) => {
    const reasons = [];
    if (focus.triggers.always) reasons.push('always');
    for (const file of files) {
      for (const path of [file.old_path, file.new_path].filter((value) => typeof value === 'string' && value.length)) {
        for (const rule of focus.triggers.any_of ?? []) {
          if (rule.path_patterns.some((pattern) => glob(pattern, path)) &&
            (!rule.extensions || rule.extensions.some((extension) => path.endsWith(extension)))) {
            reasons.push(`matched ${file.id}: ${path}`);
          }
        }
      }
    }
    return reasons.length ? [{ focusId: focus.id, reasons: [...new Set(reasons)] }] : [];
  });
}

function assertPacket(packet, packetRef) {
  if (!packet || !['current', 'staged', 'unstaged', 'branch', 'pr'].includes(packet.scope) ||
    typeof packet.repo !== 'string' || typeof packet.cwd !== 'string' ||
    !Array.isArray(packet.changed_files) || !Array.isArray(packet.hunks) ||
    !/^sha256:[a-f0-9]{64}$/.test(packet.packet_digest ?? '')) {
    throw new Error('Invalid frozen evidence packet');
  }
  if (!isAbsolute(packetRef)) throw new Error('Evidence packet reference must be absolute');
  if (packet.changed_files.length === 0) throw new Error('No changes to review');
}

export function buildDynamicReviewArgs({ invocation, packet, packetRef, reactOverlay } = {}) {
  assertPacket(packet, packetRef);
  if (!invocation || !['parallel', 'single', 'focus'].includes(invocation.mode)) {
    throw new Error('Invalid parsed review invocation');
  }
  const automatic = automaticSelection(packet);
  let selected;
  let excluded;
  if (invocation.mode === 'single') {
    selected = [{ focusId: 'general', reasons: ['single general review'],
      applicableFocusIds: automatic.map(({ focusId }) => focusId) }];
    excluded = [];
  } else if (invocation.mode === 'focus') {
    if (!REVIEW_FOCUSES.some(({ id }) => id === invocation.focusId)) throw new Error('Unknown selected focus');
    if (invocation.reactOverlayRequested && !(reactOverlay?.applicable)) {
      throw new Error('React focus requires applicable frozen framework evidence');
    }
    selected = [{ focusId: invocation.focusId, reasons: [`explicit focus: ${invocation.focusId}`] }];
    excluded = REVIEW_FOCUSES.filter(({ id }) => id !== invocation.focusId)
      .map(({ id }) => ({ focusId: id, reason: `excluded by explicit ${invocation.focusId} filter` }));
  } else {
    selected = automatic;
    excluded = REVIEW_FOCUSES.filter(({ id }) => !selected.some(({ focusId }) => focusId === id))
      .map(({ id }) => ({ focusId: id, reason: 'no changed path matched this focus trigger' }));
  }
  if (selected.length === 0) throw new Error('No review focus selected');

  const fileIds = packet.changed_files.map(({ id }) => id);
  const hunkIds = packet.hunks.map(({ id }) => id);
  const digestId = packet.packet_digest.slice('sha256:'.length, 'sha256:'.length + 16);
  const selectedArgs = selected.map((entry, index) => ({
    focusId: entry.focusId,
    invocationId: `${digestId}-${index + 1}-${entry.focusId}`,
    fileIds,
    hunkIds,
    ...(entry.applicableFocusIds ? { applicableFocusIds: entry.applicableFocusIds } : {}),
    selectionReasons: entry.reasons,
  }));
  const scope = {
    mode: invocation.mode,
    type: packet.scope,
    legacySyntax: invocation.legacySyntax === true,
    reactOverlayRequested: invocation.reactOverlayRequested === true,
    ...(invocation.prUrl ? { prUrl: invocation.prUrl } : {}),
    ...(packet.scope_detail ? { detail: packet.scope_detail } : {}),
  };
  const performanceSelected = selectedArgs.some(({ focusId }) => focusId === 'performance');
  return {
    version: 1,
    repo: packet.repo,
    cwd: packet.cwd,
    scope,
    packetRef,
    packetDigest: packet.packet_digest,
    selected: selectedArgs,
    excluded,
    ...(performanceSelected && reactOverlay?.applicable ? { reactOverlay: {
      applicable: true,
      skillRoot: reactOverlay.skillRoot,
      revision: reactOverlay.revision,
      ruleIds: [...reactOverlay.ruleIds],
      ...(reactOverlay.integrityError ? { integrityError: reactOverlay.integrityError } : {}),
    } } : {}),
  };
}

export async function inspectReviewerPolicy(reviewerPath = join(
  process.env.PI_CODING_AGENT_DIR ?? join(homedir(), '.pi', 'agent'),
  'agents',
  'reviewer.md',
)) {
  const content = await readFile(reviewerPath, 'utf8');
  const frontmatter = content.match(/^---\n([\s\S]*?)\n---(?:\n|$)/);
  if (!frontmatter) throw new Error('Reviewer agent frontmatter is missing');
  const model = frontmatter[1].match(/^model:\s*(.+)$/m)?.[1]?.trim();
  const thinking = frontmatter[1].match(/^thinking:\s*(.+)$/m)?.[1]?.trim();
  if (model !== REVIEWER_MODEL || thinking !== REVIEWER_THINKING) {
    throw new Error(`Reviewer route must be ${REVIEWER_MODEL} with ${REVIEWER_THINKING} thinking`);
  }
  return { digest: sha(Buffer.from(content)), model, thinking };
}

function withPreparationMetadata(packet, reviewer, reactOverlay) {
  const prepared = JSON.parse(JSON.stringify(packet));
  delete prepared.packet_digest;
  prepared.reviewer_policy = reviewer;
  if (reactOverlay?.applicable) prepared.react_overlay = {
    applicable: true,
    skillRoot: reactOverlay.skillRoot,
    revision: reactOverlay.revision,
    ruleIds: [...reactOverlay.ruleIds],
    ...(reactOverlay.integrityError ? { integrityError: reactOverlay.integrityError } : {}),
  };
  prepared.packet_digest = sha(Buffer.from(JSON.stringify(prepared)));
  return prepared;
}

export function defaultPacketDirectory() {
  const agentDir = process.env.PI_CODING_AGENT_DIR ?? join(homedir(), '.pi', 'agent');
  return join(agentDir, 'review-packets');
}

export async function persistEvidencePacket(packet, packetDir = defaultPacketDirectory()) {
  await mkdir(packetDir, { recursive: true, mode: 0o700 });
  const name = `${packet.packet_digest.slice('sha256:'.length)}.json`;
  const root = await realpath(packetDir);
  const path = join(root, name);
  const bytes = Buffer.from(JSON.stringify(packet));
  let handle;
  try {
    handle = await open(path, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY, 0o600);
    await handle.writeFile(bytes);
    await handle.sync();
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
    const info = await lstat(path);
    if (!info.isFile() || info.isSymbolicLink()) throw new Error('Evidence packet destination is a symlink or non-regular file');
    const existingHandle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
    let existing;
    try { existing = await existingHandle.readFile(); }
    finally { await existingHandle.close(); }
    if (!existing.equals(bytes)) throw new Error('Evidence packet digest collision');
  } finally {
    await handle?.close();
  }
  return path;
}

export async function prepareReviewEvidence({
  invocation,
  cwd,
  packetDir = defaultPacketDirectory(),
  reactSkillRoot = join(homedir(), '.agents', 'skills', 'vercel-react-best-practices'),
  reviewerPath,
} = {}, dependencies = {}) {
  const parsed = parseReviewText(invocation ?? '');
  const captureLocal = dependencies.captureLocal ?? captureLocalEvidence;
  const captureBranch = dependencies.captureBranch ?? captureBranchEvidence;
  const capturePr = dependencies.capturePr ?? capturePrEvidence;
  const inspectReviewer = dependencies.inspectReviewer ?? inspectReviewerPolicy;
  const loadReactRules = dependencies.loadReactRules ?? loadPinnedReactRules;
  const persistPacket = dependencies.persistPacket ?? persistEvidencePacket;

  const reviewer = await inspectReviewer(reviewerPath);
  let packet;
  if (parsed.scope === 'pr') packet = await capturePr({ repo: cwd, url: parsed.prUrl });
  else if (parsed.scope === 'branch') packet = await captureBranch({ repo: cwd });
  else packet = await captureLocal({ repo: cwd, scope: parsed.scope });

  const reactApplicable = Array.isArray(packet.framework_context?.applicableFileIds)
    && packet.framework_context.applicableFileIds.length > 0;
  const reactOverlay = loadReactRules(reactSkillRoot, { applicable: reactApplicable });
  const preparedPacket = withPreparationMetadata(packet, reviewer, reactOverlay);
  await mkdir(packetDir, { recursive: true, mode: 0o700 });
  const canonicalPacketDir = await realpath(packetDir);
  const packetRef = join(canonicalPacketDir, `${preparedPacket.packet_digest.slice('sha256:'.length)}.json`);
  const workflowArgs = buildDynamicReviewArgs({ invocation: parsed, packet: preparedPacket, packetRef, reactOverlay });
  const persistedRef = await persistPacket(preparedPacket, canonicalPacketDir);
  if (persistedRef !== packetRef) throw new Error('Evidence packet persisted at an unexpected path');
  return {
    workflowArgs,
    packetRef,
    snapshot: {
      scope: preparedPacket.scope,
      baseSha: preparedPacket.base_sha,
      headSha: preparedPacket.head_sha,
      snapshotId: preparedPacket.snapshot_id,
      packetDigest: preparedPacket.packet_digest,
    },
    reviewer,
  };
}

export async function verifyPreparedReview({ packetRef, cwd, packetDir = defaultPacketDirectory() } = {}, dependencies = {}) {
  if (typeof packetRef !== 'string' || !isAbsolute(packetRef)) throw new Error('An absolute packetRef is required');
  const root = await realpath(packetDir);
  const path = resolve(packetRef);
  if (path !== root && !path.startsWith(`${root}${sep}`)) throw new Error('packetRef is outside the review packet directory');
  const info = await lstat(path);
  if (!info.isFile() || info.isSymbolicLink()) throw new Error('Evidence packet is a symlink or non-regular file');
  const handle = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW);
  let packetBytes;
  try { packetBytes = await handle.readFile(); }
  finally { await handle.close(); }
  const packet = JSON.parse(packetBytes.toString('utf8'));
  const expectedDigest = packet.packet_digest;
  delete packet.packet_digest;
  const actualDigest = sha(Buffer.from(JSON.stringify(packet)));
  packet.packet_digest = expectedDigest;
  if (actualDigest !== expectedDigest) return { valid: false, reason: 'Evidence packet digest changed' };

  const inspectReviewer = dependencies.inspectReviewer ?? inspectReviewerPolicy;
  const currentReviewer = await inspectReviewer();
  if (packet.reviewer_policy?.digest !== currentReviewer.digest) {
    return { valid: false, reason: 'Reviewer policy changed during review' };
  }
  if (packet.react_overlay?.applicable) {
    const loadReactRules = dependencies.loadReactRules ?? loadPinnedReactRules;
    const current = loadReactRules(packet.react_overlay.skillRoot, { applicable: true });
    if (current.integrityError || current.revision !== packet.react_overlay.revision ||
      JSON.stringify(current.ruleIds) !== JSON.stringify(packet.react_overlay.ruleIds)) {
      return { valid: false, reason: 'React rule inventory changed during review' };
    }
  }
  const verifySnapshot = dependencies.verifySnapshot ?? verifyEvidenceSnapshot;
  return verifySnapshot(packet, { cwd });
}

export async function executeReviewEvidenceTool(params, ctx, dependencies = {}) {
  if (!params || !ctx || typeof ctx.cwd !== 'string') throw new Error('Review evidence tool context is invalid');
  if (params.action === 'prepare') {
    if (typeof params.invocation !== 'string') throw new Error('prepare requires invocation');
    const prepare = dependencies.prepare ?? prepareReviewEvidence;
    const result = await prepare({ invocation: params.invocation, cwd: ctx.cwd });
    const launch = {
      name: 'pi-review',
      args: result.workflowArgs,
      background: true,
      maxAgents: result.workflowArgs.selected.length * 2 + 1,
      concurrency: 4,
    };
    return {
      content: [{
        type: 'text',
        text: `Prepared ${result.workflowArgs.selected.length} review focus(es). Packet: ${result.packetRef}\nWorkflow launch JSON:\n${JSON.stringify(launch)}`,
      }],
      details: result,
    };
  }
  if (params.action === 'verify') {
    if (typeof params.packetRef !== 'string') throw new Error('verify requires packetRef');
    const verify = dependencies.verify ?? verifyPreparedReview;
    const result = await verify({ packetRef: params.packetRef, cwd: ctx.cwd });
    return {
      content: [{ type: 'text', text: result.valid ? 'Review evidence is still current.' : `Review evidence is stale: ${result.reason}` }],
      details: result,
      ...(result.valid ? {} : { isError: true }),
    };
  }
  throw new Error('action must be prepare or verify');
}
