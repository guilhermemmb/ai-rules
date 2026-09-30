import assert from 'node:assert/strict';
import { test } from 'node:test';

const moduleUrl = new URL('../pi-config/skills/review-pipeline/framework.mjs', import.meta.url);
async function collect(input) {
  return (await import(moduleUrl)).collectFrameworkContext(input);
}
function reader(files) {
  return async path => files[path] ? { bytes: Buffer.from(files[path]), ref: `fixture:${path}` } : null;
}
const reactManifest = JSON.stringify({ dependencies: { react: '19.0.0' } });
const nextManifest = JSON.stringify({ dependencies: { next: '16.0.0' } });

test('selects JSX and hooks from their nearest React/Next package manifests', async () => {
  const result = await collect({ repoRoot: '', layers: [{ name: 'worktree' }], readAt: reader({
    'apps/web/package.json': reactManifest, 'apps/next/package.json': nextManifest,
  }), changedFiles: [
    { id: 'f1', new_path: 'apps/web/components/Card.tsx' },
    { id: 'f2', new_path: 'apps/web/hooks/useFeed.ts' },
    { id: 'f3', new_path: 'apps/next/app/page.tsx' },
  ] });
  assert.equal(result.status, 'resolved');
  assert.deepEqual(result.applicableFileIds, ['f1', 'f2', 'f3']);
  assert.deepEqual(result.packages.map(row => [row.root, row.react, row.next]), [
    ['apps/next', false, true], ['apps/web', true, false],
  ]);
  assert.ok(result.packages.every(row => /^sha256:[a-f0-9]{64}$/.test(row.sha256)));
});

test('does not leak root React identity into a non-React monorepo package', async () => {
  const result = await collect({ repoRoot: '', layers: [{ name: 'worktree' }], readAt: reader({
    'package.json': reactManifest, 'packages/plain/package.json': JSON.stringify({ name: 'plain' }),
  }), changedFiles: [{ id: 'f1', new_path: 'packages/plain/Widget.tsx' }] });
  assert.equal(result.status, 'resolved');
  assert.deepEqual(result.applicableFileIds, []);
  assert.deepEqual(result.unresolvedFileIds, []);
});

test('generic TypeScript needs resolved React package evidence and candidates fail closed when manifests are missing', async () => {
  const resolved = await collect({ repoRoot: '', layers: [{ name: 'index' }], readAt: reader({
    'src/package.json': reactManifest,
  }), changedFiles: [{ id: 'f1', new_path: 'src/data.ts' }] });
  assert.deepEqual(resolved.applicableFileIds, ['f1']);
  const incomplete = await collect({ repoRoot: '', layers: [{ name: 'pr-head' }], readAt: reader({}),
    changedFiles: [{ id: 'f2', new_path: 'src/components/Widget.tsx' }, { id: 'f3', new_path: 'scripts/release.ts' }] });
  assert.equal(incomplete.status, 'incomplete');
  assert.deepEqual(incomplete.unresolvedFileIds, ['f2']);
  assert.match(incomplete.limitations[0], /f2/);
});

test('uses provided revision reader rather than an unrelated local checkout', async () => {
  const reads = [];
  const result = await collect({ repoRoot: '', layers: [{ name: 'pr-head', ref: 'abc' }],
    readAt: async (path, layer) => { reads.push([path, layer.name, layer.ref]); return path === 'app/package.json'
      ? { bytes: Buffer.from(nextManifest), ref: 'git:abc:app/package.json' } : null; },
    changedFiles: [{ id: 'f1', new_path: 'app/page.tsx' }] });
  assert.deepEqual(result.applicableFileIds, ['f1']);
  assert.ok(reads.every(([, name, ref]) => name === 'pr-head' && ref === 'abc'));
  assert.equal(result.packages[0].manifestRef, 'git:abc:app/package.json');
});
