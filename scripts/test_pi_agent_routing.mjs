import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { test } from 'node:test';

const userRoot = `${homedir()}/.pi/agent`;
const packageRoot = `${userRoot}/npm/node_modules/pi-subagents/agents`;
const repoRoot = new URL('../pi-config/', import.meta.url);
const assignments = {
  coordinator: ['openai-codex/gpt-6-luna', 'low'],
  thinker: ['openai-codex/gpt-5.6-sol', 'medium'],
  reviewer: ['openai-codex/gpt-5.6-terra', 'medium'],
  worker: ['openai-codex/gpt-6-luna', 'off'],
  oracle: ['openai-codex/gpt-6-sol', 'off'],
  scout: ['openai-codex/gpt-6-luna', 'medium'],
  delegate: ['openai-codex/gpt-6-luna', 'low'],
  researcher: ['openai-codex/gpt-5.6-terra', 'medium'],
  'evidence-auditor': ['openai-codex/gpt-5.6-terra', 'high'],
};
function parts(path) {
  assert.ok(existsSync(path), `Missing managed definition: ${path}`);
  const source = readFileSync(path, 'utf8');
  assert.ok(source.startsWith('---\n'));
  const [, frontmatter, body] = source.split(/^---\s*$/m);
  return { frontmatter, body };
}

test('one effective model and thinking assignment lives in each native agent definition', () => {
  for (const [role, [model, thinking]] of Object.entries(assignments)) {
    for (const root of [new URL('agents/', repoRoot), new URL(`file://${userRoot}/agents/`)]) {
      const { frontmatter } = parts(new URL(`${role}.md`, root));
      assert.deepEqual(frontmatter.match(/^model:\s*(.+)$/gm), [`model: ${model}`], role);
      assert.deepEqual(frontmatter.match(/^thinking:\s*(.+)$/gm), [`thinking: ${thinking}`], role);
    }
  }
  assert.equal(existsSync(new URL('agents/advisor.md', repoRoot)), false, 'Advisor must remain an oracle alias');
});

test('package builtin shadow definitions retain full prompt and safety/context metadata', () => {
  for (const role of ['worker', 'oracle', 'scout', 'delegate', 'researcher', 'evidence-auditor']) {
    const builtin = parts(`${packageRoot}/${role}.md`);
    const managed = parts(new URL(`agents/${role}.md`, repoRoot));
    assert.equal(managed.body, builtin.body, `${role} builtin prompt must not be lost`);
    for (const key of ['tools', 'acceptanceRole', 'systemPromptMode', 'defaultContext', 'inheritSkills', 'output']) {
      const line = builtin.frontmatter.split('\n').find(row => row.startsWith(`${key}:`));
      if (line) assert.ok(managed.frontmatter.includes(line), `${role} must preserve ${key}`);
    }
  }
});

test('settings and profile stop duplicating model policy without changing user settings or tools', () => {
  const read = path => JSON.parse(readFileSync(path, 'utf8'));
  const repo = read(new URL('settings.json', repoRoot));
  const installed = read(`${userRoot}/settings.json`);
  const comparableRepo = structuredClone(repo);
  const dynamicWorkflowPackage = 'npm:@quintinshaw/pi-dynamic-workflows@3.13.1';
  if (!installed.packages.some(entry => (typeof entry === 'string' ? entry : entry.source) === dynamicWorkflowPackage)) {
    comparableRepo.packages = comparableRepo.packages.filter(entry => entry !== dynamicWorkflowPackage);
  }
  assert.deepEqual(installed, comparableRepo);
  assert.equal(repo.defaultModel, 'gpt-5.6-terra');
  assert.equal(repo.defaultProvider, 'openai-codex');
  for (const entry of Object.values(repo.subagents.agentOverrides)) {
    assert.equal(Object.hasOwn(entry, 'model'), false);
    assert.equal(Object.hasOwn(entry, 'thinking'), false);
    assert.ok(entry.tools?.length);
    assert.ok(entry.extensions?.length);
  }
  const normalized = structuredClone(repo);
  for (const entry of Object.values(normalized.subagents.agentOverrides)) {
    delete entry.model;
    delete entry.thinking;
  }
  const canonical = value => JSON.stringify(value, (_key, entry) => entry && typeof entry === 'object' && !Array.isArray(entry)
    ? Object.fromEntries(Object.entries(entry).sort(([a], [b]) => a.localeCompare(b))) : entry);
  assert.equal(createHash('sha256').update(canonical(normalized)).digest('hex'),
    '5514df69d87c0725e7a0fc5c281cb4f1f5d43b275ba4a743af4ea4963b608ab2');
  for (const path of [new URL('profiles/pi-subagents/superpowers.json', repoRoot), `${userRoot}/profiles/pi-subagents/superpowers.json`]) {
    const profile = read(path);
    for (const entry of Object.values(profile.subagents?.agentOverrides ?? {})) {
      assert.equal(Object.hasOwn(entry, 'model'), false);
      assert.equal(Object.hasOwn(entry, 'thinking'), false);
    }
  }
});

test('coordinator and slash template use agent-definition routing rather than hardcoded role models', () => {
  const coordinator = parts(new URL('agents/coordinator.md', repoRoot)).body;
  assert.doesNotMatch(coordinator, /thinker openai-codex|reviewer openai-codex/);
  const prompt = parts(new URL('prompts/superpowers-multi.md', repoRoot)).frontmatter;
  assert.doesNotMatch(prompt, /^model:/m);
});
