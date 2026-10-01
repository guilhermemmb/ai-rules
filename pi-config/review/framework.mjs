import { createHash } from 'node:crypto';
import { dirname, posix } from 'node:path';

const sha256 = bytes => `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
const normal = path => path?.replaceAll('\\', '/').replace(/^\.\//, '') ?? '';
const sourcePath = file => normal(file.new_path ?? file.old_path);
const isJsTs = path => /\.(?:[cm]?[jt]sx?)$/i.test(path);
const needsManifest = path => /\.(?:[cm]?jsx?|tsx)$/i.test(path) ||
  /(?:^|\/)use[A-Z][^/]*\.(?:[cm]?[jt]sx?)$/i.test(path) ||
  /(?:^|\/)(?:app|pages)(?:\/|$)/.test(path);
const dependencies = manifest => ({ ...manifest.dependencies, ...manifest.devDependencies, ...manifest.peerDependencies, ...manifest.optionalDependencies });

export async function collectFrameworkContext({ repoRoot = '', changedFiles, layers, readAt }) {
  if (!Array.isArray(changedFiles) || !Array.isArray(layers) || !layers.length || typeof readAt !== 'function') {
    throw new Error('Invalid framework evidence inputs');
  }
  const layer = layers[0];
  const packages = new Map();
  const applicableFileIds = [];
  const unresolvedFileIds = [];
  const limitations = [];
  for (const file of changedFiles) {
    const path = sourcePath(file);
    if (!file?.id || !isJsTs(path)) continue;
    let directory = posix.dirname(path);
    let found = null;
    while (directory !== '.' && directory !== '/' && !directory.startsWith('../')) {
      const manifestPath = normal(posix.join(directory, 'package.json'));
      const evidence = await readAt(manifestPath, layer);
      if (evidence) {
        try {
          const manifest = JSON.parse(Buffer.from(evidence.bytes).toString('utf8'));
          const deps = dependencies(manifest);
          found = { root: directory, manifestRef: evidence.ref, sha256: sha256(evidence.bytes),
            react: typeof deps.react === 'string', next: typeof deps.next === 'string' };
          packages.set(directory, found);
        } catch {
          if (needsManifest(path)) {
            unresolvedFileIds.push(file.id);
            limitations.push(`${file.id}: invalid package manifest at ${manifestPath}`);
          }
        }
        break;
      }
      directory = posix.dirname(directory);
    }
    if (!found) {
      const evidence = await readAt('package.json', layer);
      if (evidence) {
        try {
          const manifest = JSON.parse(Buffer.from(evidence.bytes).toString('utf8'));
          const deps = dependencies(manifest);
          found = { root: '.', manifestRef: evidence.ref, sha256: sha256(evidence.bytes),
            react: typeof deps.react === 'string', next: typeof deps.next === 'string' };
          packages.set('.', found);
        } catch {
          if (needsManifest(path)) {
            unresolvedFileIds.push(file.id);
            limitations.push(`${file.id}: invalid package manifest at package.json`);
          }
        }
      }
    }
    if (!found) {
      if (needsManifest(path)) {
        unresolvedFileIds.push(file.id);
        limitations.push(`${file.id}: no package manifest resolved from ${path} at ${layer.name}`);
      }
    } else if (found.react || found.next) applicableFileIds.push(file.id);
  }
  return { status: unresolvedFileIds.length ? 'incomplete' : 'resolved',
    packages: [...packages.values()].sort((a, b) => a.root.localeCompare(b.root)),
    applicableFileIds, unresolvedFileIds, limitations };
}
