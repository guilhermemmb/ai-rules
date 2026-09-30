import assert from 'node:assert/strict';
import { existsSync, readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { homedir, tmpdir } from 'node:os';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { test } from 'node:test';

const skill = new URL('../pi-config/skills/review-pipeline/', import.meta.url);
const registry = JSON.parse(readFileSync(new URL('pipeline.json', skill)));
const moduleUrl = new URL('validate.mjs', skill);
async function validator() {
  assert.ok(existsSync(moduleUrl), 'Pi report validator must be implemented');
  return import(moduleUrl);
}
const versionFile = `${homedir()}/.pi/agent/install/current-version`;
const coreRoot = process.env.PI_CORE_ROOT || (existsSync(versionFile)
  ? `${homedir()}/.pi/agent/install/releases/${readFileSync(versionFile, 'utf8').trim()}/node_modules/@earendil-works/pi-coding-agent` : '');
const promptModule = `${coreRoot}/dist/core/prompt-templates.js`;

test('real Pi template expansion preserves PR URL, filter, and extra arguments for validation', {
  skip: !existsSync(promptModule),
}, async () => {
  const { substituteArgs } = await import(pathToFileURL(promptModule));
  const template = readFileSync(new URL('../pi-config/prompts/review.md', import.meta.url), 'utf8');
  for (const [args, expected] of [
    [[], ''],
    [['branch', 'security'], 'branch security'],
    [['pr', 'https://github.com/example/repo/pull/7', 'security'], 'pr https://github.com/example/repo/pull/7 security'],
    [['branch', 'Design Consistency'], 'branch Design Consistency'],
    [['branch', 'security', 'unexpected'], 'branch security unexpected'],
  ]) {
    const expanded = substituteArgs(template, args);
    assert.ok(expanded.split('\n').some(line => line === `Load the \`review-pipeline\` skill. Review invocation: ${expected}`), `Missing invocation: ${expected}`);
  }
});

function file(path, oldPath = null) {
  return { id: 'f1', old_path: oldPath, new_path: path, status: oldPath ? 'R' : 'A', binary: false };
}

test('selection covers TS accessibility hooks and configuration correctness', async () => {
  const { selectFocuses } = await validator();
  for (const path of ['src/hooks/useDialog.ts', 'utils/restoreFocus.ts', 'src/useReducedMotion.ts', 'src/keyboard.js']) {
    assert.ok(selectFocuses(registry, [file(path)]).selected.some(row => row.id === 'accessibility'), path);
  }
  for (const path of ['package.json', '.github/workflows/ci.yml', 'config/settings.toml', 'Dockerfile', '.env.example']) {
    assert.ok(selectFocuses(registry, [file(path)]).selected.some(row => row.id === 'correctness'), path);
  }
  assert.equal(selectFocuses(registry, [file('src/account.ts')]).selected.some(row => row.id === 'accessibility'), false);
});

test('selection honors old rename paths, root globs, same-file extension constraints, and filters', async () => {
  const { selectFocuses } = await validator();
  assert.ok(selectFocuses(registry, [file('lib/dialog.ts', 'hooks/dialog.ts')]).selected.some(row => row.id === 'accessibility'));
  assert.ok(selectFocuses(registry, [file('components/App.tsx')]).selected.some(row => row.id === 'design-consistency'));
  const tiny = { focuses: [{ id: 'focused', label: 'Focused', triggers: { any_of: [{ path_patterns: ['**/hooks/**'], extensions: ['.ts'] }] } }] };
  assert.equal(selectFocuses(tiny, [file('hooks/readme.md'), { ...file('src/app.ts'), id: 'f2' }]).selected.length, 0);
  const filtered = selectFocuses(registry, [file('README.md')], 'SECURITY');
  assert.deepEqual(filtered.selected.map(row => row.id), ['security']);
  assert.ok(filtered.excluded.includes('git-safety'));
  assert.equal(filtered.filtered, true);
  assert.throws(() => selectFocuses(registry, [file('x.ts')], 'unknown-focus'), /filter/);
});

function finding(overrides = {}) {
  return { severity: 'important', confidence: 0.9, file: 'src/app.ts', line: 11, end_line: 11,
    side: 'new', hunk_id: 'h1', issue: 'Null access', impact: 'Crashes on empty input',
    fix: 'Guard empty input', category: 'null-safety', ...overrides };
}
function bundle() {
  return {
    packet: { packet_digest: `sha256:${'a'.repeat(64)}`, complete: true,
      changed_files: [{ ...file('src/app.ts'), old_path: 'src/app.ts', status: 'M' }],
      hunks: [{ id: 'h1', file_id: 'f1', old_start: 10, old_count: 3, new_start: 10, new_count: 3 }] },
    expected: [{ focusId: 'correctness', invocationId: 'i1', runId: 'r1' }],
    configuredIdentity: { model: 'test/model', thinking: 'medium' },
    runtimeIdentities: { r1: { model: 'test/model:medium', thinking: 'medium' } },
    results: [{ key: 'correctness', focusId: 'correctness', invocationId: 'i1', packetDigest: `sha256:${'a'.repeat(64)}`,
      runId: 'r1', ok: true, structuredOutput: {
        focus_id: 'correctness', invocation_id: 'i1', packet_digest: `sha256:${'a'.repeat(64)}`,
        success: true, summary: 'Reviewed.', coverage: { reviewed_file_ids: ['f1'], omitted_file_ids: [], reviewed_hunk_ids: ['h1'], omitted_hunk_ids: [] },
        findings: [], findings_omitted: 0, strengths: [], errors: [],
      } }],
    evidenceDecisions: [],
  };
}
async function check(data) {
  return (await validator()).validateReviewBundle(data);
}
function accept(data, index = 0) {
  data.evidenceDecisions.push({ runId: 'r1', findingIndex: index, decision: 'accept', reason: 'Parent traced empty input into the changed dereference.' });
}

test('React lens requires frozen framework applicability and never broadens non-React selection', async () => {
  const { selectFocuses } = await validator();
  const files = [file('packages/web/hooks/useFeed.ts')];
  const selected = selectFocuses(registry, files, null, {
    status: 'resolved', applicableFileIds: ['f1'], unresolvedFileIds: [], limitations: [],
  });
  assert.ok(selected.selected.some(row => row.id === 'react-best-practices'));
  assert.equal(selected.selected.filter(row => row.id === 'react-best-practices').length, 1);
  const plain = selectFocuses(registry, files, null, {
    status: 'resolved', applicableFileIds: [], unresolvedFileIds: [], limitations: [],
  });
  assert.equal(plain.selected.some(row => row.id === 'react-best-practices'), false);
  const unresolved = selectFocuses(registry, files, null, {
    status: 'incomplete', applicableFileIds: [], unresolvedFileIds: ['f1'], limitations: ['f1: manifest unavailable'],
  });
  assert.deepEqual(unresolved.limitations, ['f1: manifest unavailable']);
  assert.throws(() => selectFocuses(registry, files, 'react-best-practices', {
    status: 'resolved', applicableFileIds: [], unresolvedFileIds: [], limitations: [],
  }), /applicable|React/i);
});

test('React findings require a pinned Vercel rule ID that matches its category family', async () => {
  const { validateReviewBundle } = await validator();
  const input = bundle();
  input.expected = [{ focusId: 'react-best-practices', invocationId: 'i-react' }];
  input.results[0].key = 'react-best-practices';
  input.results[0].focusId = 'react-best-practices';
  input.results[0].invocationId = 'i-react';
  input.results[0].structuredOutput.focus_id = 'react-best-practices';
  input.results[0].structuredOutput.invocation_id = 'i-react';
  input.results[0].structuredOutput.findings = [finding({ category: 'async' })];
  input.reactRuleIds = ['async-parallel', 'bundle-barrel-imports'];
  let output = await validateReviewBundle(input);
  assert.match(output.lanes[0].errors.join('\n'), /rule_id/i);
  input.results[0].structuredOutput.findings[0].rule_id = 'bundle-barrel-imports';
  output = await validateReviewBundle(input);
  assert.match(output.lanes[0].errors.join('\n'), /category/i);
  input.results[0].structuredOutput.findings[0].rule_id = 'async-parallel';
  output = await validateReviewBundle(input);
  assert.equal(output.lanes[0].errors.some(error => /rule_id|category/i.test(error)), false);
});

test('complete matching reports pass while preserving AI review provenance', async () => {
  const result = await check(bundle());
  assert.equal(result.verdict, 'Passes Review');
  assert.equal(result.coverage, 'complete');
  assert.deepEqual(result.counts, { selected: 1, dispatched: 1, completed: 1, inconclusive: 0 });
});

test('schema is authoritative: malformed, extra and missing fields fail closed', async () => {
  for (const mutate of [
    b => delete b.results[0].structuredOutput.summary,
    b => b.results[0].structuredOutput.acceptanceReport = {},
    b => b.results[0].structuredOutput.findings.push(finding({ confidence: 90 })),
    b => b.results[0].structuredOutput.findings.push(finding({ severity: 'P1' })),
    b => b.results[0].structuredOutput = null,
  ]) {
    const data = bundle(); mutate(data);
    const result = await check(data);
    assert.equal(result.verdict, 'Inconclusive');
    assert.equal(result.findings.length, 0);
  }
});

test('fixed-keyword schema validates nested report constraints without a runtime installation', async () => {
  const { validateReportSchema } = await validator();
  const schema = JSON.parse(readFileSync(new URL('report.schema.json', skill)));
  const valid = bundle().results[0].structuredOutput;
  assert.equal(validateReportSchema(schema, valid).status, 'valid');
  const invalid = [
    report => delete report.coverage.reviewed_file_ids,
    report => report.coverage.extra = true,
    report => report.coverage.reviewed_file_ids = ['f1', 'f1'],
    report => report.findings = [finding({ line: 0 })],
    report => report.findings = [finding({ line: '11' })],
    report => report.findings = [finding({ confidence: 1.01 })],
    report => report.findings = [finding({ severity: 'major' })],
    report => report.packet_digest = 'sha256:invalid',
  ];
  for (const mutate of invalid) {
    const report = structuredClone(valid); mutate(report);
    assert.equal(validateReportSchema(schema, report).status, 'invalid');
  }
  assert.throws(() => validateReportSchema({ ...schema, unevaluatedProperties: false }, valid), /unsupported schema keyword/i);
});

test('fixed-keyword report schema agrees with the installed runtime on representative reports', {
  skip: !existsSync(`${homedir()}/.pi/agent/npm/node_modules/pi-subagents/src/runs/shared/structured-output.js`),
}, async t => {
  const { validateStructuredOutputValue } = await import(pathToFileURL(`${homedir()}/.pi/agent/npm/node_modules/pi-subagents/src/runs/shared/structured-output.js`));
  const { validateReportSchema } = await validator();
  const schema = JSON.parse(readFileSync(new URL('report.schema.json', skill)));
  const original = bundle().results[0].structuredOutput;
  for (const mutate of [() => {}, r => { r.findings = [finding({ line: null, end_line: null, side: 'file', hunk_id: null })]; },
    r => { r.coverage.reviewed_file_ids.push('f1'); }, r => { r.findings_omitted = -1; },
    r => { r.summary = ''; }, r => { r.findings = [finding({ confidence: 2 })]; }]) {
    const report = structuredClone(original); mutate(report);
    let runtime;
    try { runtime = await validateStructuredOutputValue(schema, report); }
    catch (error) { t.skip(`Installed validator unavailable: ${error.message}`); return; }
    assert.equal(validateReportSchema(schema, report).status, runtime.status);
  }
});

test('general review accepts applicable cross-lens categories and rejects unrelated ones', async () => {
  const data = bundle();
  data.expected[0].focusId = 'general';
  data.expected[0].applicableFocusIds = (await validator()).selectFocuses(registry, data.packet.changed_files).selected.map(row => row.id);
  Object.assign(data.results[0], { key: 'general', focusId: 'general' });
  data.results[0].structuredOutput.focus_id = 'general';
  data.results[0].structuredOutput.findings = [finding({ category: 'auth' })];
  accept(data);
  assert.equal((await check(data)).verdict, 'Needs Work');
  data.results[0].structuredOutput.findings[0].category = 'tokens';
  const rejected = await check(data);
  assert.equal(rejected.verdict, 'Inconclusive');
  assert.match(rejected.lanes[0].errors.join(' '), /category/i);
  data.expected[0].applicableFocusIds = ['unknown'];
  await assert.rejects(check(data), /applicable/i);
  data.expected[0].applicableFocusIds = ['correctness', 'security'];
  await assert.rejects(check(data), /applicable/i);
});

test('production schema check works with a missing private runtime root', async () => {
  const prior = process.env.PI_SUBAGENTS_ROOT;
  process.env.PI_SUBAGENTS_ROOT = '/missing/pi-subagents';
  try { assert.equal((await check(bundle())).verdict, 'Passes Review'); }
  finally { if (prior === undefined) delete process.env.PI_SUBAGENTS_ROOT; else process.env.PI_SUBAGENTS_ROOT = prior; }
});

test('failed, stale, swapped, duplicate, unexpected and unlaunched results never pass', async () => {
  for (const mutate of [
    b => b.results[0].ok = false,
    b => b.results[0].structuredOutput.packet_digest = `sha256:${'b'.repeat(64)}`,
    b => b.results[0].structuredOutput.invocation_id = 'wrong',
    b => b.results[0].key = 'security',
    b => b.results.push(structuredClone(b.results[0])),
    b => b.results.push({ ...structuredClone(b.results[0]), runId: 'unexpected' }),
    b => b.results = [],
    b => b.runtimeIdentities.r1.model = 'another/model',
    b => delete b.runtimeIdentities.r1,
    b => b.packet.complete = false,
  ]) {
    const data = bundle(); mutate(data);
    assert.equal((await check(data)).verdict, 'Inconclusive');
  }
});

test('coverage requires exact partition of the frozen file and hunk inventory', async () => {
  for (const mutate of [
    c => c.reviewed_file_ids.push('unknown'),
    c => c.reviewed_hunk_ids.push('h1'),
    c => c.omitted_hunk_ids.push('h1'),
    c => c.reviewed_hunk_ids = [],
    c => { c.reviewed_hunk_ids = []; c.omitted_hunk_ids = ['h1']; },
  ]) {
    const data = bundle(); mutate(data.results[0].structuredOutput.coverage);
    assert.equal((await check(data)).verdict, 'Inconclusive');
  }
});

test('finding locations and categories are checked against actual packet metadata', async () => {
  for (const change of [
    { file: 'unrelated.ts' }, { line: 99, end_line: 99 }, { end_line: 10 },
    { hunk_id: 'unknown' }, { category: 'tokens' },
    { side: 'file', line: 1, end_line: 1, hunk_id: 'h1' },
  ]) {
    const data = bundle(); data.results[0].structuredOutput.findings = [finding(change)]; accept(data);
    const result = await check(data);
    assert.equal(result.verdict, 'Inconclusive');
    assert.equal(result.findings.length, 0);
  }
});

test('important findings require parent evidence decisions, then deterministically block', async () => {
  const data = bundle(); data.results[0].structuredOutput.findings = [finding()];
  const pending = await check(data);
  assert.equal(pending.verdict, 'Inconclusive');
  assert.equal(pending.candidates.length, 1);
  accept(data);
  const result = await check(data);
  assert.equal(result.verdict, 'Needs Work');
  assert.equal(result.findings[0].provenance[0].runId, 'r1');
});

test('partial valid findings remain actionable without claiming complete coverage', async () => {
  const data = bundle(); const report = data.results[0].structuredOutput;
  report.success = false; report.errors = ['One file could not be read'];
  report.findings = [finding()]; accept(data);
  const result = await check(data);
  assert.equal(result.verdict, 'Needs Work');
  assert.equal(result.coverage, 'incomplete');
  assert.equal(result.findings[0].partial, true);
});

test('suggestions and rejected false positives do not block complete reviews', async () => {
  const data = bundle(); data.results[0].structuredOutput.findings = [finding({ severity: 'suggestion' })]; accept(data);
  assert.equal((await check(data)).verdict, 'Passes Review');
  data.results[0].structuredOutput.findings[0].severity = 'important';
  data.evidenceDecisions[0] = { runId: 'r1', findingIndex: 0, decision: 'reject', reason: 'Caller already rejects empty input.' };
  const result = await check(data);
  assert.equal(result.verdict, 'Passes Review');
  assert.equal(result.rejected.length, 1);
  assert.equal(result.findings.length, 0);
});

test('unknown or duplicate evidence decisions cannot manufacture approval', async () => {
  const data = bundle(); data.results[0].structuredOutput.findings = [finding()]; accept(data);
  data.evidenceDecisions.push({ ...data.evidenceDecisions[0] });
  assert.equal((await check(data)).verdict, 'Inconclusive');
});

test('old-side deletions and binary file-level findings retain proper anchors', async () => {
  const data = bundle();
  data.results[0].structuredOutput.findings = [finding({ side: 'old' })]; accept(data);
  assert.equal((await check(data)).verdict, 'Needs Work');
  data.expected[0].focusId = 'git-safety';
  Object.assign(data.results[0], { key: 'git-safety', focusId: 'git-safety' });
  data.results[0].structuredOutput.focus_id = 'git-safety';
  data.packet.changed_files[0].binary = true;
  data.packet.hunks = [];
  data.results[0].structuredOutput.coverage.reviewed_hunk_ids = [];
  data.results[0].structuredOutput.findings = [finding({ side: 'file', line: null, end_line: null, hunk_id: null, category: 'binary' })];
  assert.equal((await check(data)).verdict, 'Needs Work');
});

test('CLI distinguishes passing, incomplete and malformed inputs without a private runtime', () => {
  const dir = mkdtempSync(join(tmpdir(), 'pi-review-validation-'));
  const path = join(dir, 'input.json');
  const run = (command, value, env = process.env) => {
    writeFileSync(path, JSON.stringify(value));
    return spawnSync(process.execPath, [fileURLToPath(moduleUrl), command, path], { encoding: 'utf8', env });
  };
  try {
    const pass = run('reconcile', bundle());
    assert.equal(pass.status, 0, pass.stderr);
    assert.equal(JSON.parse(pass.stdout).verdict, 'Passes Review');
    const incomplete = run('reconcile', { ...bundle(), results: [] });
    assert.equal(incomplete.status, 1);
    assert.equal(JSON.parse(incomplete.stdout).verdict, 'Inconclusive');
    const withoutRuntime = run('reconcile', bundle(), { ...process.env, PI_SUBAGENTS_ROOT: join(dir, 'missing-runtime') });
    assert.equal(withoutRuntime.status, 0, withoutRuntime.stderr);
    assert.equal(JSON.parse(withoutRuntime.stdout).verdict, 'Passes Review');
    const select = run('select', { changed_files: [file('settings.yaml')], filter: 'correctness' });
    assert.equal(select.status, 0, select.stderr);
    assert.deepEqual(JSON.parse(select.stdout).selected.map(row => row.id), ['correctness']);
    assert.equal(run('reconcile', {}).status, 2);
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

test('malformed manifests and duplicate packet inventories are rejected rather than normalized', async () => {
  for (const mutate of [
    b => b.expected.push(structuredClone(b.expected[0])),
    b => b.packet.changed_files.push(structuredClone(b.packet.changed_files[0])),
    b => b.packet.hunks[0].file_id = 'missing',
    b => b.configuredIdentity = {},
    b => b.evidenceDecisions = {},
  ]) {
    const data = bundle(); mutate(data);
    await assert.rejects(check(data));
  }
});

test('deduplication retains cross-focus provenance and highest supported severity', async () => {
  const data = bundle();
  data.results[0].structuredOutput.findings = [finding({ category: 'logic', severity: 'suggestion' })]; accept(data);
  const second = structuredClone(data.results[0]);
  Object.assign(second, { invocationId: 'i2', runId: 'r2' });
  Object.assign(second.structuredOutput, { invocation_id: 'i2' });
  // Two invocations for one focus are invalid; use a second lens with a shared location/issue/fix.
  Object.assign(second, { key: 'maintainability', focusId: 'maintainability' });
  second.structuredOutput.focus_id = 'maintainability';
  Object.assign(second.structuredOutput.findings[0], { category: 'tests', severity: 'important' });
  data.expected.push({ focusId: 'maintainability', invocationId: 'i2', runId: 'r2' });
  data.results.push(second); data.runtimeIdentities.r2 = data.runtimeIdentities.r1;
  data.evidenceDecisions.push({ runId: 'r2', findingIndex: 0, decision: 'accept', reason: 'Same regression independently confirmed.' });
  const result = await check(data);
  assert.equal(result.findings.length, 1);
  assert.equal(result.findings[0].severity, 'important');
  assert.equal(result.findings[0].provenance.length, 2);
});
