#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { constants } from 'node:fs';
import { copyFile, lstat, mkdir, open, readFile, realpath, rename } from 'node:fs/promises';
import { register } from 'node:module';
import { homedir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const sha = (bytes) => `sha256:${createHash('sha256').update(bytes).digest('hex')}`;

function defaultRuntimeRoot() {
  if (process.env.PI_DYNAMIC_WORKFLOWS_ROOT) return process.env.PI_DYNAMIC_WORKFLOWS_ROOT;
  const agentDir = process.env.PI_CODING_AGENT_DIR ?? join(homedir(), '.pi', 'agent');
  return join(agentDir, 'npm', 'node_modules', '@quintinshaw', 'pi-dynamic-workflows');
}

async function defaultHostNodeModules() {
  const agentDir = process.env.PI_CODING_AGENT_DIR_FOR_HOST ?? join(homedir(), '.pi', 'agent');
  const version = (await readFile(join(agentDir, 'install', 'current-version'), 'utf8')).trim();
  return join(agentDir, 'install', 'releases', version, 'node_modules');
}

function registerHostPeerLoader(hostNodeModules) {
  const mappings = {
    '@earendil-works/pi-coding-agent': pathToFileURL(join(hostNodeModules, '@earendil-works', 'pi-coding-agent', 'dist', 'index.js')).href,
    '@earendil-works/pi-tui': pathToFileURL(join(hostNodeModules, '@earendil-works', 'pi-tui', 'dist', 'index.js')).href,
    typebox: pathToFileURL(join(hostNodeModules, 'typebox', 'build', 'index.mjs')).href,
    'typebox/value': pathToFileURL(join(hostNodeModules, 'typebox', 'build', 'value', 'index.mjs')).href,
  };
  const loader = `const mappings = ${JSON.stringify(mappings)};\nexport async function resolve(specifier, context, nextResolve) {\n  if (mappings[specifier]) return { url: mappings[specifier], shortCircuit: true };\n  return nextResolve(specifier, context);\n}`;
  register(`data:text/javascript,${encodeURIComponent(loader)}`, import.meta.url);
}

async function loadParser(runtimeRoot, hostNodeModules) {
  const packageJson = JSON.parse(await readFile(join(runtimeRoot, 'package.json'), 'utf8'));
  if (packageJson.version !== '3.13.1') {
    throw new Error(`Dynamic Workflows 3.13.1 is required; found ${packageJson.version ?? 'unknown'}`);
  }
  const entry = pathToFileURL(join(runtimeRoot, 'dist', 'index.js')).href;
  try {
    return (await import(entry)).parseWorkflowScript;
  } catch (error) {
    if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error;
    registerHostPeerLoader(hostNodeModules ?? await defaultHostNodeModules());
    return (await import(`${entry}?host-peers=1`)).parseWorkflowScript;
  }
}

function sourceFilePath(sourcePath) {
  return sourcePath instanceof URL ? fileURLToPath(sourcePath) : resolve(sourcePath);
}

async function existingRegularFile(path) {
  try {
    const info = await lstat(path);
    if (!info.isFile() || info.isSymbolicLink()) {
      throw new Error('Saved workflow destination is a symlink or non-regular file');
    }
    return true;
  } catch (error) {
    if (error.code === 'ENOENT') return false;
    throw error;
  }
}

async function writeAtomic(path, bytes) {
  const directory = dirname(path);
  const temporary = join(directory, `.${basename(path)}.${process.pid}.${Date.now()}.tmp`);
  let handle;
  try {
    handle = await open(temporary, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY, 0o600);
    await handle.writeFile(bytes);
    await handle.sync();
    await handle.close();
    handle = undefined;
    await rename(temporary, path);
    const directoryHandle = await open(directory, constants.O_RDONLY);
    try { await directoryHandle.sync(); }
    finally { await directoryHandle.close(); }
  } finally {
    await handle?.close();
    try {
      const info = await lstat(temporary);
      if (info.isFile()) await import('node:fs/promises').then(({ unlink }) => unlink(temporary));
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
}

export async function installSavedReviewWorkflow({
  sourcePath,
  homeDir = homedir(),
  runtimeRoot = defaultRuntimeRoot(),
  now = () => new Date().toISOString(),
  backupDir,
  hostNodeModules,
} = {}) {
  if (!sourcePath) throw new Error('sourcePath is required');
  const sourceFile = sourceFilePath(sourcePath);
  const source = await readFile(sourceFile, 'utf8');
  const parseWorkflowScript = await loadParser(runtimeRoot, hostNodeModules);
  const { meta } = parseWorkflowScript(source);
  if (meta.name !== 'pi-review' || typeof meta.description !== 'string' || !meta.description.trim()) {
    throw new Error('Workflow source must declare pi-review metadata');
  }

  const requestedDirectory = resolve(homeDir, '.pi', 'workflows', 'saved');
  await mkdir(requestedDirectory, { recursive: true, mode: 0o700 });
  const directory = await realpath(requestedDirectory);
  const path = join(directory, 'pi-review.json');
  const digest = sha(Buffer.from(source));
  const exists = await existingRegularFile(path);
  let previous = null;
  if (exists) {
    previous = JSON.parse(await readFile(path, 'utf8'));
    if (previous.name === 'pi-review' && previous.description === meta.description && previous.script === source &&
      previous.location === 'user' && previous.source === 'user' && previous.path === path) {
      return { path, digest, changed: false };
    }
    if (backupDir) {
      await mkdir(backupDir, { recursive: true, mode: 0o700 });
      await copyFile(path, join(backupDir, `pi-review-${sha(Buffer.from(JSON.stringify(previous))).slice(7)}.json`),
        constants.COPYFILE_EXCL);
    }
  }

  const record = {
    name: 'pi-review',
    description: meta.description,
    script: source,
    location: 'user',
    source: 'user',
    path,
    savedAt: now(),
  };
  await writeAtomic(path, Buffer.from(`${JSON.stringify(record, null, 2)}\n`));
  return { path, digest, changed: true };
}

async function main(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!value || !['--source', '--home', '--runtime-root', '--backup-dir', '--host-node-modules'].includes(flag)) {
      throw new Error('Usage: install_pi_dynamic_review.mjs --source <path> [--home <dir>] [--runtime-root <dir>] [--backup-dir <dir>] [--host-node-modules <dir>]');
    }
    if (flag === '--source') options.sourcePath = value;
    else if (flag === '--home') options.homeDir = value;
    else if (flag === '--runtime-root') options.runtimeRoot = value;
    else if (flag === '--backup-dir') options.backupDir = value;
    else options.hostNodeModules = value;
  }
  const result = await installSavedReviewWorkflow(options);
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
