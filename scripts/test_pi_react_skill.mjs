import assert from 'node:assert/strict';
import { cpSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';

const globalRoot = `${process.env.HOME}/.agents/skills/vercel-react-best-practices`;
const moduleUrl = new URL('../pi-config/review/react-rules.mjs', import.meta.url);

async function rules(root = globalRoot) {
  assert.ok(existsSync(moduleUrl), 'Pinned React rule verifier is missing');
  return (await import(moduleUrl)).loadPinnedReactRules(root);
}

test('global Pi React skill is pinned and has a complete Vercel rule inventory', async () => {
  const result = await rules();
  assert.equal(result.applicable, true);
  assert.equal(result.skillRoot, globalRoot);
  assert.equal(result.revision, '063bee94c3f4df8453406c830b0a7df0f2860278');
  assert.equal(result.metadataVersion, '1.0.0');
  assert.equal(result.ruleIds.length, 70);
  assert.ok(result.ruleIds.includes('async-parallel'));
  assert.ok(result.ruleIds.includes('rerender-no-inline-components'));
  assert.ok(result.ruleIds.every(id => !id.startsWith('_')));
  assert.ok(Object.keys(result.hashes).includes('SKILL.md'));
});

test('tampered, missing, and extra pinned React rule files fail closed', async t => {
  const fixture = mkdtempSync(join(tmpdir(), 'pi-react-rules-'));
  t.after(() => rmSync(fixture, { recursive: true, force: true }));
  const root = join(fixture, 'vercel-react-best-practices');
  const reset = () => { rmSync(root, { recursive: true, force: true }); cpSync(globalRoot, root, { recursive: true }); };
  reset();
  writeFileSync(join(root, 'rules', 'async-parallel.md'), 'tampered');
  assert.match((await rules(root)).integrityError, /hash|integrity/i);
  reset();
  rmSync(join(root, 'rules', 'async-parallel.md'));
  assert.match((await rules(root)).integrityError, /missing|inventory/i);
  reset();
  writeFileSync(join(root, 'rules', 'extra-rule.md'), '# unexpected');
  assert.match((await rules(root)).integrityError, /extra|inventory/i);
});

test('non-applicable framework evidence does not require the skill installation', async () => {
  const { loadPinnedReactRules } = await import(moduleUrl);
  assert.deepEqual(loadPinnedReactRules('/missing/skill', { applicable: false }), {
    applicable: false,
    skillRoot: '/missing/skill',
    revision: '063bee94c3f4df8453406c830b0a7df0f2860278',
    ruleIds: [],
  });
});

test('repository mirror is byte-identical to the verified global installation', async () => {
  const provenance = JSON.parse(readFileSync(join(globalRoot, 'provenance.json'), 'utf8'));
  assert.equal(provenance.source.repository, 'https://github.com/vercel-labs/agent-skills');
  assert.equal(provenance.source.revision, '063bee94c3f4df8453406c830b0a7df0f2860278');
  assert.equal(provenance.skill.name, 'vercel-react-best-practices');
  const mirror = 'pi-config/vercel-react-best-practices';
  assert.ok(existsSync(join(mirror, 'SKILL.md')));
  assert.deepEqual(JSON.parse(readFileSync(join(mirror, 'provenance.json'), 'utf8')), provenance);
});
