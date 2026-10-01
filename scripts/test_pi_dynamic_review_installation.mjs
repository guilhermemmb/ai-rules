import assert from 'node:assert/strict';
import { cpSync, existsSync, lstatSync, mkdtempSync, readFileSync, readdirSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { test } from 'node:test';

const root = new URL('../', import.meta.url);
const settingsPath = new URL('../pi-config/settings.json', import.meta.url);
const promptPath = new URL('../pi-config/prompts/review.md', import.meta.url);
const reviewerPath = new URL('../pi-config/agents/reviewer.md', import.meta.url);
const workflowPath = new URL('../pi-config/workflows/pi-review.js', import.meta.url);
const installerPath = new URL('./install_pi_dynamic_review.mjs', import.meta.url);
const extensionPath = new URL('../pi-config/extensions/review-evidence.ts', import.meta.url);
const runtimeRoot = process.env.PI_DYNAMIC_WORKFLOWS_ROOT
  ?? join(tmpdir(), 'pi-dynamic-workflows-3.13.1', 'node_modules', '@quintinshaw', 'pi-dynamic-workflows');

function frontmatter(source) {
  const match = source.match(/^---\n([\s\S]*?)\n---(?:\n|$)/);
  assert.ok(match, 'frontmatter is required');
  return match[1];
}

test('settings declare one exact Dynamic Workflows package pin', () => {
  const settings = JSON.parse(readFileSync(settingsPath, 'utf8'));
  const matches = settings.packages.filter((entry) =>
    (typeof entry === 'string' ? entry : entry.source)?.startsWith('npm:@quintinshaw/pi-dynamic-workflows'));
  assert.deepEqual(matches, ['npm:@quintinshaw/pi-dynamic-workflows@3.13.1']);
});

test('/review prepares evidence, starts pi-review in background, and verifies delivery', () => {
  const prompt = readFileSync(promptPath, 'utf8');
  assert.match(frontmatter(prompt), /argument-hint: "\[parallel\|single\|focus\] \[current\|branch\|staged\|unstaged\|pr <url>\]"/);
  assert.match(prompt, /review_evidence/);
  assert.match(prompt, /action:\s*["`]?prepare/);
  assert.match(prompt, /model-visible `Workflow launch JSON`/);
  assert.match(prompt, /exact `name`, `args`, `background`, `maxAgents`, and `concurrency` fields/);
  assert.match(prompt, /Do not reconstruct arguments from the packet/);
  assert.match(prompt, /action:\s*["`]?verify/);
  assert.match(prompt, /snapshot|stale/i);
  assert.doesNotMatch(prompt, /review-pipeline/);
  assert.doesNotMatch(prompt, /openai-codex|gpt-5\.6-terra/);
});

test('reviewer remains the sole Terra/medium read-only policy source', () => {
  const reviewer = readFileSync(reviewerPath, 'utf8');
  const header = frontmatter(reviewer);
  assert.deepEqual(header.match(/^model:\s*(.+)$/gm), ['model: openai-codex/gpt-5.6-terra']);
  assert.deepEqual(header.match(/^thinking:\s*(.+)$/gm), ['thinking: medium']);
  const tools = header.match(/^tools:\s*(.+)$/m)?.[1].split(',').map((tool) => tool.trim()) ?? [];
  for (const forbidden of ['bash', 'edit', 'write']) assert.equal(tools.includes(forbidden), false);
  assert.match(reviewer, /one assigned focus/i);
  assert.match(reviewer, /frozen (?:evidence )?packet/i);
  assert.match(reviewer, /Do not .*launch (?:more|additional) (?:reviewers|agents)/i);

  const workflow = readFileSync(workflowPath, 'utf8');
  assert.doesNotMatch(workflow, /\b(?:model|tier)\s*:/);
  assert.match(workflow, /agentType:\s*"reviewer"/);
});

test('review-evidence extension registers the typed parent tool', async () => {
  const agentRoot = join(homedir(), '.pi', 'agent');
  const version = readFileSync(join(agentRoot, 'install', 'current-version'), 'utf8').trim();
  const hostModules = join(agentRoot, 'install', 'releases', version, 'node_modules');
  const { createJiti } = await import(pathToFileURL(join(hostModules, 'jiti', 'lib', 'jiti.mjs')).href);
  const jiti = createJiti(import.meta.url, { moduleCache: false, alias: {
    '@earendil-works/pi-ai': join(hostModules, '@earendil-works', 'pi-ai', 'dist', 'index.js'),
    '@earendil-works/pi-coding-agent': join(hostModules, '@earendil-works', 'pi-coding-agent', 'dist', 'index.js'),
  } });
  const extension = await jiti.import(fileURLToPath(extensionPath));
  let registered;
  extension.default({ registerTool(tool) { registered = tool; } });
  assert.equal(registered.name, 'review_evidence');
  assert.deepEqual(Object.keys(registered.parameters.properties), ['action', 'invocation', 'packetRef']);
  assert.deepEqual(registered.parameters.properties.action.anyOf.map(({ const: value }) => value), ['prepare', 'verify']);
});

test('installer writes an idempotent valid user saved-workflow record atomically', async (t) => {
  const homeDir = mkdtempSync(join(tmpdir(), 'pi-review-home-'));
  const fixtureDir = mkdtempSync(join(tmpdir(), 'pi-review-source-'));
  t.after(() => {
    rmSync(homeDir, { recursive: true, force: true });
    rmSync(fixtureDir, { recursive: true, force: true });
  });
  const sourcePath = join(fixtureDir, 'pi-review.js');
  cpSync(workflowPath, sourcePath);
  const { installSavedReviewWorkflow } = await import(installerPath);
  const first = await installSavedReviewWorkflow({
    sourcePath,
    homeDir,
    runtimeRoot,
    now: () => '2026-10-01T10:00:00.000Z',
  });
  assert.equal(first.changed, true);
  assert.equal(existsSync(first.path), true);
  assert.equal(lstatSync(first.path).isFile(), true);
  const record = JSON.parse(readFileSync(first.path, 'utf8'));
  assert.deepEqual(Object.keys(record), ['name', 'description', 'script', 'location', 'source', 'path', 'savedAt']);
  assert.equal(record.name, 'pi-review');
  assert.equal(record.location, 'user');
  assert.equal(record.source, 'user');
  assert.equal(record.path, first.path);
  assert.equal(record.savedAt, '2026-10-01T10:00:00.000Z');
  assert.equal(record.script, readFileSync(sourcePath, 'utf8'));
  assert.match(first.digest, /^sha256:[a-f0-9]{64}$/);

  const second = await installSavedReviewWorkflow({
    sourcePath,
    homeDir,
    runtimeRoot,
    now: () => '2026-10-01T11:00:00.000Z',
  });
  assert.deepEqual(second, { ...first, changed: false });
  assert.equal(JSON.parse(readFileSync(first.path, 'utf8')).savedAt, record.savedAt);

  writeFileSync(sourcePath, `${readFileSync(sourcePath, 'utf8')}\n// installation-change\n`);
  const third = await installSavedReviewWorkflow({
    sourcePath,
    homeDir,
    runtimeRoot,
    now: () => '2026-10-01T12:00:00.000Z',
  });
  assert.equal(third.changed, true);
  assert.notEqual(third.digest, first.digest);
  assert.equal(JSON.parse(readFileSync(first.path, 'utf8')).savedAt, '2026-10-01T12:00:00.000Z');
  assert.deepEqual(readdirSync(join(homeDir, '.pi', 'workflows', 'saved')), ['pi-review.json']);
  assert.equal(existsSync(join(homeDir, '.pi', 'workflows', 'runs')), false);
});

test('installer validates a Pi-managed package whose host peers are external', async (t) => {
  const fixture = mkdtempSync(join(tmpdir(), 'pi-review-managed-package-'));
  const homeDir = join(fixture, 'home');
  const managedRoot = join(fixture, 'node_modules', '@quintinshaw', 'pi-dynamic-workflows');
  t.after(() => rmSync(fixture, { recursive: true, force: true }));
  cpSync(runtimeRoot, managedRoot, { recursive: true });
  cpSync(join(runtimeRoot, '..', '..', 'acorn'), join(fixture, 'node_modules', 'acorn'), { recursive: true });
  const hostNodeModules = '/Users/guilhermebomfim/.pi/agent/install/releases/0.99.2/node_modules';
  const { installSavedReviewWorkflow } = await import(installerPath);
  const result = await installSavedReviewWorkflow({
    sourcePath: workflowPath,
    homeDir,
    runtimeRoot: managedRoot,
    hostNodeModules,
  });
  assert.equal(result.changed, true);
  assert.equal(existsSync(result.path), true);
});

test('installer refuses a symlink saved-workflow destination', async (t) => {
  const homeDir = mkdtempSync(join(tmpdir(), 'pi-review-home-'));
  const savedDir = join(homeDir, '.pi', 'workflows', 'saved');
  const outside = join(homeDir, 'outside.json');
  t.after(() => rmSync(homeDir, { recursive: true, force: true }));
  await import('node:fs/promises').then(({ mkdir }) => mkdir(savedDir, { recursive: true }));
  writeFileSync(outside, '{}');
  symlinkSync(outside, join(savedDir, 'pi-review.json'));
  const { installSavedReviewWorkflow } = await import(installerPath);
  await assert.rejects(
    installSavedReviewWorkflow({ sourcePath: workflowPath, homeDir, runtimeRoot }),
    /symlink|regular/i,
  );
});
