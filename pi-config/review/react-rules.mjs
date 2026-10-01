import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const APPROVED_REVISION = '063bee94c3f4df8453406c830b0a7df0f2860278';

function filesUnder(root, directory = root) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? filesUnder(root, path) : entry.isFile() ? [relative(root, path)] : [];
  }).sort();
}

function verifyPinnedReactRules(skillRoot) {
  let provenance;
  try { provenance = JSON.parse(readFileSync(join(skillRoot, 'provenance.json'), 'utf8')); }
  catch { throw new Error('Pinned React skill provenance is missing or invalid'); }
  if (provenance?.source?.repository !== 'https://github.com/vercel-labs/agent-skills' ||
    provenance.source.revision !== APPROVED_REVISION ||
    provenance?.skill?.name !== 'vercel-react-best-practices' || provenance?.skill?.metadataVersion !== '1.0.0' ||
    !provenance.files || typeof provenance.files !== 'object') {
    throw new Error('Pinned React skill provenance does not match the approved source');
  }
  const actual = filesUnder(skillRoot).filter(path => path !== 'provenance.json');
  const expected = Object.keys(provenance.files).sort();
  if (actual.length !== expected.length || actual.some((path, index) => path !== expected[index])) {
    throw new Error('Pinned React skill file inventory is missing or has unexpected files');
  }
  for (const path of expected) {
    if (sha256(readFileSync(join(skillRoot, path))) !== provenance.files[path]) {
      throw new Error(`Pinned React skill integrity hash mismatch: ${path}`);
    }
  }
  const skill = readFileSync(join(skillRoot, 'SKILL.md'), 'utf8');
  if (!/^name:\s*vercel-react-best-practices\s*$/m.test(skill)) throw new Error('Pinned React skill name is invalid');
  const metadata = JSON.parse(readFileSync(join(skillRoot, 'metadata.json'), 'utf8'));
  if (String(metadata.version) !== provenance.skill.metadataVersion) throw new Error('Pinned React skill metadata version is invalid');
  const ruleIds = expected.filter(path => path.startsWith('rules/') && path.endsWith('.md'))
    .map(path => path.slice('rules/'.length, -'.md'.length)).filter(id => !id.startsWith('_')).sort();
  if (ruleIds.length !== 70 || new Set(ruleIds).size !== ruleIds.length) throw new Error('Pinned React rule inventory is invalid');
  return { applicable: true, revision: provenance.source.revision, skillRoot,
    metadataVersion: provenance.skill.metadataVersion, ruleIds, hashes: provenance.files };
}

export function loadPinnedReactRules(skillRoot, { applicable = true } = {}) {
  if (!applicable) return { applicable: false, skillRoot, revision: APPROVED_REVISION, ruleIds: [] };
  try {
    return verifyPinnedReactRules(skillRoot);
  } catch (error) {
    return { applicable: true, skillRoot, revision: APPROVED_REVISION, ruleIds: [], integrityError: error.message };
  }
}
