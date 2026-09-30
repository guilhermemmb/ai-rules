import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { test } from 'node:test';
import { pathToFileURL } from 'node:url';

const skill = new URL('../pi-config/skills/review-pipeline/', import.meta.url);
const command = new URL('command.mjs', skill);
const registry = JSON.parse(readFileSync(new URL('pipeline.json', skill), 'utf8'));

async function parse(tokens, catalog = registry) {
  assert.ok(existsSync(command), 'The review command parser is missing');
  return (await import(command)).parseReviewInvocation(tokens, catalog);
}

const current = { mode: 'parallel', focusId: null, scope: 'current', prUrl: null, legacySyntax: false };
test('bare /review defaults to parallel current changes', async () => {
  assert.deepEqual(await parse([]), current);
  assert.deepEqual(await parse(['parallel']), current);
  assert.deepEqual(await parse(['current']), current);
});

test('single selects one general review and focus shorthand selects one focused review', async () => {
  assert.deepEqual(await parse(['single']), { ...current, mode: 'single' });
  assert.deepEqual(await parse(['simplify']), { ...current, mode: 'focus', focusId: 'simplicity' });
  assert.deepEqual(await parse(['SECURITY']), { ...current, mode: 'focus', focusId: 'security' });
});

test('PR, branch, and legacy target-first focus forms preserve target identity', async () => {
  const url = 'https://github.com/example/repo/pull/42';
  assert.deepEqual(await parse(['pr', url]), { ...current, scope: 'pr', prUrl: url });
  assert.deepEqual(await parse(['single', 'pr', url]), { ...current, mode: 'single', scope: 'pr', prUrl: url });
  assert.deepEqual(await parse(['simplify', 'branch']), { ...current, mode: 'focus', focusId: 'simplicity', scope: 'branch' });
  assert.deepEqual(await parse(['branch', 'security']), { ...current, mode: 'focus', focusId: 'security', scope: 'branch', legacySyntax: true });
});

test('ambiguous aliases, unknown tokens, and malformed targets fail closed', async () => {
  for (const tokens of [['pr'], ['single', 'pr'], ['parallel', 'security'], ['unknown'], ['branch', 'security', 'extra'], ['pr', 'not-a-url']]) {
    await assert.rejects(parse(tokens), /usage|invalid|ambiguous/i, tokens.join(' '));
  }
  for (const bad of [
    { ...registry, focuses: [...registry.focuses, { id: 'SECURITY', label: 'Duplicate', triggers: {} }] },
    { ...registry, focuses: registry.focuses.map(focus => focus.id === 'simplicity' ? { ...focus, aliases: ['single'] } : focus) },
  ]) {
    await assert.rejects(parse([], bad), /duplicate|collid|ambiguous/i);
  }
});

test('single and named-focus launches use one native background reviewer without policy overrides', async () => {
  assert.ok(existsSync(new URL('launch.mjs', skill)), 'Review launch builder is missing');
  const { buildReviewerLaunch } = await import(new URL('launch.mjs', skill));
  const common = { selectedFocuses: [{ id: 'correctness' }, { id: 'security' }],
    packetRef: '/tmp/review-evidence.json', packetDigest: `sha256:${'a'.repeat(64)}`,
    assignedIds: { files: ['f1'], hunks: ['h1'] },
    focusTexts: { general: 'General lens', correctness: 'Correctness lens', security: 'Security lens' },
    schema: { type: 'object', required: ['findings'] }, cwd: '/tmp/repository' };
  for (const invocation of [await parse(['single']), await parse(['security'])]) {
    const launch = buildReviewerLaunch({ ...common, invocation });
    assert.equal(launch.kind, 'direct');
    assert.equal(launch.subagentArgs.agent, 'reviewer');
    assert.equal(launch.subagentArgs.async, true);
    assert.equal(launch.subagentArgs.context, 'fresh');
    assert.equal(launch.subagentArgs.outputMode, 'inline');
    assert.equal(launch.subagentArgs.output, false);
    assert.deepEqual(launch.subagentArgs.acceptance, { level: 'attested', report: 'on' });
    assert.deepEqual(launch.subagentArgs.outputSchema, common.schema);
    for (const key of ['model', 'thinking', 'tools', 'extensions']) assert.equal(Object.hasOwn(launch.subagentArgs, key), false);
    assert.match(launch.subagentArgs.task, /\/tmp\/review-evidence\.json/);
    assert.match(launch.subagentArgs.task, /f1.*h1/s);
    assert.deepEqual(launch.expected.map(row => row.focusId), [invocation.mode === 'single' ? 'general' : 'security']);
    if (invocation.mode === 'single') assert.deepEqual(launch.expected[0].applicableFocusIds, ['correctness', 'security']);
  }
});

test('parallel launch binds one canonical native workflow with four reviewer slots', async () => {
  assert.ok(existsSync(new URL('launch.mjs', skill)), 'Review launch builder is missing');
  const { buildReviewerLaunch } = await import(new URL('launch.mjs', skill));
  const selectedFocuses = registry.focuses.map(focus => ({ id: focus.id }));
  const launch = buildReviewerLaunch({ invocation: await parse([]), selectedFocuses,
    packetRef: '/tmp/evidence.json', packetDigest: `sha256:${'a'.repeat(64)}`,
    assignedIds: { files: ['f1'], hunks: ['h1'] },
    focusTexts: Object.fromEntries(registry.focuses.map(focus => [focus.id, `Lens ${focus.id}`])),
    reactSkill: { skillRoot: `${process.env.HOME}/.agents/skills/vercel-react-best-practices`,
      revision: '063bee94c3f4df8453406c830b0a7df0f2860278', ruleIds: ['async-parallel'] },
    schema: { type: 'object' }, cwd: '/tmp/repository' });
  assert.equal(launch.kind, 'workflow');
  assert.equal(launch.subagentArgs.async, true);
  assert.equal(launch.subagentArgs.globalConcurrencyLimit, 4);
  assert.equal(launch.subagentArgs.args.maxConcurrency, 4);
  assert.equal(launch.subagentArgs.args.lanes.length, 9);
  assert.match(launch.subagentArgs.workflowScriptPath, /review-pipeline\/dispatch\.js$/);
  for (const key of ['agent', 'model', 'thinking', 'tools']) assert.equal(Object.hasOwn(launch.subagentArgs, key), false);
  assert.equal(JSON.stringify(launch.subagentArgs).includes('raw sensitive packet'), false);
});

test('React focus requires verified global Vercel skill metadata and references its rule directory', async () => {
  const { buildReviewerLaunch } = await import(new URL('launch.mjs', skill));
  const react = registry.focuses.find(focus => focus.id === 'react-best-practices');
  const common = { invocation: await parse(['react-best-practices']), selectedFocuses: [react],
    packetRef: '/tmp/evidence.json', packetDigest: `sha256:${'a'.repeat(64)}`,
    assignedIds: { files: ['f1'], hunks: ['h1'] }, focusTexts: { 'react-best-practices': 'React lens' },
    schema: { type: 'object' }, cwd: '/tmp/repository' };
  assert.throws(() => buildReviewerLaunch(common), /React skill/i);
  const launch = buildReviewerLaunch({ ...common, reactSkill: {
    skillRoot: `${process.env.HOME}/.agents/skills/vercel-react-best-practices`,
    revision: '063bee94c3f4df8453406c830b0a7df0f2860278', ruleIds: ['async-parallel'],
  } });
  assert.equal(launch.kind, 'direct');
  assert.match(launch.subagentArgs.task, /vercel-react-best-practices\/SKILL\.md/);
  assert.match(launch.subagentArgs.task, /rules/);
  assert.match(launch.subagentArgs.task, /063bee94c3f4df8453406c830b0a7df0f2860278/);
  for (const key of ['model', 'thinking', 'tools', 'extensions']) assert.equal(Object.hasOwn(launch.subagentArgs, key), false);
});

test('the real Pi prompt template forwards the entire invocation as one command', {
  skip: !existsSync(`${homedir()}/.pi/agent/install/current-version`),
}, async () => {
  const version = readFileSync(`${homedir()}/.pi/agent/install/current-version`, 'utf8').trim();
  const path = `${homedir()}/.pi/agent/install/releases/${version}/node_modules/@earendil-works/pi-coding-agent/dist/core/prompt-templates.js`;
  const { substituteArgs } = await import(pathToFileURL(path).href);
  const template = readFileSync(new URL('../pi-config/prompts/review.md', import.meta.url), 'utf8');
  const body = template.split('---\n').slice(2).join('---\n');
  for (const [args, expected] of [
    [[], ''],
    [['single'], 'single'],
    [['simplify', 'branch'], 'simplify branch'],
    [['pr', 'https://github.com/example/repo/pull/42'], 'pr https://github.com/example/repo/pull/42'],
  ]) {
    const expanded = substituteArgs(body, args);
    assert.ok(expanded.split('\n').includes(`Load the \`review-pipeline\` skill. Review invocation: ${expected}`));
  }
});
