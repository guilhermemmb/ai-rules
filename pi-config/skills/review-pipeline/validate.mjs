// Deterministic bookkeeping for AI-subagent reviews; never a replacement reviewer.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const registry = JSON.parse(readFileSync(new URL('pipeline.json', import.meta.url)));
const reportSchema = JSON.parse(readFileSync(new URL('report.schema.json', import.meta.url)));
const text = value => typeof value === 'string' && value.trim().length > 0;
const unique = values => new Set(values).size === values.length;
const keyOf = (runId, index) => JSON.stringify([runId, index]);

function glob(pattern, path) {
  let source = '^';
  for (let i = 0; i < pattern.length; i++) {
    if (pattern.slice(i, i + 3) === '**/') { source += '(?:.*/)?'; i += 2; }
    else if (pattern.slice(i, i + 2) === '**') { source += '.*'; i++; }
    else if (pattern[i] === '*') source += '[^/]*';
    else source += pattern[i].replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }
  return new RegExp(`${source}$`).test(path.replaceAll('\\', '/'));
}

export function selectFocuses(catalog, files, filter = null) {
  if (!Array.isArray(files) || !Array.isArray(catalog.focuses)) throw new Error('Invalid focus selection inputs');
  if (filter !== null && !text(filter)) throw new Error('Invalid focus filter');
  const selected = [];
  for (const focus of catalog.focuses) {
    const reasons = [];
    if (filter !== null) {
      if ([focus.id, focus.label].some(value => value.toLowerCase().includes(filter.toLowerCase()))) reasons.push(`explicit filter: ${filter}`);
    } else {
      if (focus.triggers.always) reasons.push('always');
      for (const file of files) {
        for (const path of [file.old_path, file.new_path].filter(text)) {
          for (const rule of focus.triggers.any_of || []) {
            if (rule.path_patterns.some(pattern => glob(pattern, path)) &&
                (!rule.extensions || rule.extensions.some(extension => path.endsWith(extension)))) {
              reasons.push(`matched ${file.id}: ${path}`);
            }
          }
        }
      }
    }
    if (reasons.length) selected.push({ id: focus.id, reasons: [...new Set(reasons)] });
  }
  if (filter !== null && selected.length === 0) throw new Error('Focus filter matched no focus');
  return { filtered: filter !== null, selected, excluded: catalog.focuses.filter(focus => !selected.some(row => row.id === focus.id)).map(focus => focus.id) };
}

const SUPPORTED_SCHEMA_KEYS = new Set(['$schema', 'title', 'type', 'additionalProperties', 'required',
  'properties', 'items', 'enum', 'minLength', 'pattern', 'uniqueItems', 'minimum', 'maximum']);
function checkSchemaDefinition(schema) {
  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) throw new Error('Unsupported schema definition');
  for (const key of Object.keys(schema)) if (!SUPPORTED_SCHEMA_KEYS.has(key)) throw new Error(`Unsupported schema keyword: ${key}`);
  if (schema.properties) for (const child of Object.values(schema.properties)) checkSchemaDefinition(child);
  if (schema.items) checkSchemaDefinition(schema.items);
  if (schema.additionalProperties && typeof schema.additionalProperties === 'object') checkSchemaDefinition(schema.additionalProperties);
  if (schema.type && ![schema.type].flat().every(type => ['object', 'array', 'string', 'integer', 'number', 'boolean', 'null'].includes(type))) {
    throw new Error('Unsupported schema type');
  }
}
function schemaError(schema, value, path = '$') {
  const types = [schema.type].flat().filter(Boolean);
  const matches = type => type === 'null' ? value === null : type === 'array' ? Array.isArray(value) :
    type === 'integer' ? Number.isSafeInteger(value) : type === 'number' ? typeof value === 'number' && Number.isFinite(value) :
      type === 'object' ? value !== null && typeof value === 'object' && !Array.isArray(value) : typeof value === type;
  if (types.length && !types.some(matches)) return `${path}: invalid type`;
  if (schema.enum && !schema.enum.some(item => Object.is(item, value))) return `${path}: outside enum`;
  if (typeof value === 'string') {
    if (schema.minLength !== undefined && [...value].length < schema.minLength) return `${path}: too short`;
    if (schema.pattern && !new RegExp(schema.pattern).test(value)) return `${path}: pattern mismatch`;
  }
  if (typeof value === 'number') {
    if (schema.minimum !== undefined && value < schema.minimum) return `${path}: below minimum`;
    if (schema.maximum !== undefined && value > schema.maximum) return `${path}: above maximum`;
  }
  if (Array.isArray(value)) {
    if (schema.uniqueItems && new Set(value.map(item => JSON.stringify(item))).size !== value.length) return `${path}: duplicate items`;
    if (schema.items) for (const [index, item] of value.entries()) {
      const error = schemaError(schema.items, item, `${path}[${index}]`);
      if (error) return error;
    }
  }
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    for (const key of schema.required ?? []) if (!Object.hasOwn(value, key)) return `${path}.${key}: required`;
    for (const [key, item] of Object.entries(value)) {
      const definition = schema.properties?.[key];
      if (!definition) {
        if (schema.additionalProperties === false) return `${path}.${key}: extra property`;
        if (typeof schema.additionalProperties === 'object') {
          const error = schemaError(schema.additionalProperties, item, `${path}.${key}`);
          if (error) return error;
        }
      } else {
        const error = schemaError(definition, item, `${path}.${key}`);
        if (error) return error;
      }
    }
  }
  return null;
}
export function validateReportSchema(schema, value) {
  checkSchemaDefinition(schema);
  const message = schemaError(schema, value);
  return message ? { status: 'invalid', message } : { status: 'valid' };
}

function inventory(rows, label) {
  if (!Array.isArray(rows) || rows.some(row => !row || !text(row.id)) || !unique(rows.map(row => row.id))) {
    throw new Error(`Invalid or duplicate ${label} inventory`);
  }
  return new Map(rows.map(row => [row.id, row]));
}

function validateBundleInputs(input) {
  if (!input || !input.packet || !/^sha256:[a-f0-9]{64}$/.test(input.packet.packet_digest)) throw new Error('Invalid packet digest');
  if (!Array.isArray(input.expected) || !input.expected.length || !Array.isArray(input.results)) throw new Error('Expected invocations and results are required');
  if (input.expected.some(row => !row || !text(row.focusId) || !text(row.invocationId) ||
    !(row.focusId === 'general' || registry.focuses.some(focus => focus.id === row.focusId)))) throw new Error('Invalid expected invocation');
  const applicable = selectFocuses(registry, input.packet.changed_files).selected.map(row => row.id);
  for (const row of input.expected.filter(row => row.focusId === 'general')) {
    if (!Array.isArray(row.applicableFocusIds) || row.applicableFocusIds.length !== applicable.length ||
      !unique(row.applicableFocusIds) || row.applicableFocusIds.some(id => !applicable.includes(id))) {
      throw new Error('Invalid applicable focus IDs for general review');
    }
  }
  for (const field of ['focusId', 'invocationId']) {
    if (!unique(input.expected.map(row => row[field]))) throw new Error(`Duplicate expected ${field}`);
  }
  const runIds = input.expected.map(row => row.runId).filter(text);
  if (!unique(runIds)) throw new Error('Duplicate expected runId');
  if (!text(input.configuredIdentity?.model) || !text(input.configuredIdentity?.thinking)) throw new Error('Configured runtime identity is required');
  if (input.evidenceDecisions !== undefined && !Array.isArray(input.evidenceDecisions)) throw new Error('evidenceDecisions must be an array');
  const files = inventory(input.packet.changed_files, 'file');
  const hunks = inventory(input.packet.hunks, 'hunk');
  for (const file of files.values()) {
    if (![file.old_path, file.new_path].some(text)) throw new Error('File needs an old or new path');
  }
  for (const hunk of hunks.values()) {
    if (!files.has(hunk.file_id) || ['old_start', 'old_count', 'new_start', 'new_count'].some(field => !Number.isInteger(hunk[field]) || hunk[field] < 0)) {
      throw new Error('Invalid hunk metadata');
    }
  }
  return { files, hunks };
}

function checkCoverage(coverage, files, hunks) {
  const errors = [];
  for (const [kind, assigned] of [['file', files], ['hunk', hunks]]) {
    const reviewed = coverage[`reviewed_${kind}_ids`];
    const omitted = coverage[`omitted_${kind}_ids`];
    const combined = [...reviewed, ...omitted];
    if (!unique(combined) || combined.length !== assigned.size || combined.some(id => !assigned.has(id))) {
      errors.push(`${kind} coverage is not an exact partition of assigned IDs`);
    }
  }
  return errors;
}

function locationError(finding, focus, files, hunks) {
  if (!focus.categories.includes(finding.category)) return 'category is not allowed by this focus';
  if (finding.side === 'file') {
    if (finding.line !== null || finding.end_line !== null || finding.hunk_id !== null) return 'file-level finding must have null line/end_line/hunk_id';
    return [...files.values()].some(file => [file.old_path, file.new_path].includes(finding.file)) ? null : 'file is outside the packet';
  }
  const hunk = hunks.get(finding.hunk_id);
  const file = hunk && files.get(hunk.file_id);
  const side = finding.side;
  if (!file || file[`${side}_path`] !== finding.file) return 'hunk/file/side mismatch';
  if (!Number.isInteger(finding.line) || !Number.isInteger(finding.end_line) || finding.end_line < finding.line ||
    hunk[`${side}_count`] === 0 || finding.line < hunk[`${side}_start`] ||
    finding.end_line >= hunk[`${side}_start`] + hunk[`${side}_count`]) return 'line range is outside the hunk';
  return null;
}

function mergeFindings(accepted) {
  const groups = new Map();
  const rank = { suggestion: 0, important: 1, critical: 2 };
  for (const row of accepted) {
    const f = row.finding;
    // Conservative exact root-cause/remediation key; do not merge merely by line.
    const key = JSON.stringify([f.file, f.side, f.line, f.end_line, f.issue, f.fix]);
    const provenance = { focusId: row.focusId, invocationId: row.invocationId, runId: row.runId,
      findingIndex: row.findingIndex, confidence: f.confidence, category: f.category, impact: f.impact,
      evidenceReason: row.evidenceReason };
    const existing = groups.get(key);
    if (existing) {
      existing.provenance.push(provenance);
      existing.partial ||= row.partial;
      if (rank[f.severity] > rank[existing.severity]) existing.severity = f.severity;
    } else groups.set(key, { ...f, partial: row.partial, provenance: [provenance] });
  }
  return [...groups.values()].map((finding, index) => ({ id: `F${index + 1}`, ...finding }));
}

export async function validateReviewBundle(input) {
  const { files, hunks } = validateBundleInputs(input);
  const blockers = [];
  if (input.packet.complete !== true) blockers.push('Evidence packet is incomplete');
  const lanes = [];
  const candidates = [];
  const usedResults = new Set();
  const allRuns = input.results.map(row => row?.runId).filter(text);
  const duplicateRuns = new Set(allRuns.filter((id, index) => allRuns.indexOf(id) !== index));

  for (const expected of input.expected) {
    const matching = input.results.map((row, index) => ({ row, index })).filter(({ row }) => row?.invocationId === expected.invocationId);
    matching.forEach(({ index }) => usedResults.add(index));
    const lane = { ...expected, dispatched: matching.length > 0, complete: false, errors: [] };
    lanes.push(lane);
    if (matching.length !== 1) { lane.errors.push('Missing or duplicate result'); continue; }
    const row = matching[0].row;
    lane.runId = row.runId;
    const actual = input.runtimeIdentities?.[row.runId];
    const configured = input.configuredIdentity;
    if (!text(row.runId) || duplicateRuns.has(row.runId) || row.ok !== true || row.key !== expected.focusId || row.focusId !== expected.focusId ||
      row.packetDigest !== input.packet.packet_digest || (expected.runId && row.runId !== expected.runId)) {
      lane.errors.push('Failed runtime result or mismatched result identity'); continue;
    }
    if (!actual || actual.thinking !== configured.thinking || ![configured.model, `${configured.model}:${configured.thinking}`].includes(actual.model)) {
      lane.errors.push('Missing or mismatched observed model/thinking'); continue;
    }
    const report = row.structuredOutput;
    const schema = validateReportSchema(reportSchema, report);
    if (schema.status !== 'valid') { lane.errors.push(`Invalid report schema: ${schema.message}`); continue; }
    if (report.focus_id !== expected.focusId || report.invocation_id !== expected.invocationId || report.packet_digest !== input.packet.packet_digest) {
      lane.errors.push('Mismatched report focus/invocation/digest'); continue;
    }
    lane.errors.push(...checkCoverage(report.coverage, files, hunks));
    if (lane.errors.length) continue;
    const partial = !report.success || report.errors.length > 0 || report.findings_omitted !== 0 ||
      report.coverage.omitted_file_ids.length > 0 || report.coverage.omitted_hunk_ids.length > 0;
    if (partial) lane.errors.push('Partial report: failed review, errors, omitted findings or omitted coverage');
    lane.summary = report.summary;
    lane.strengths = report.strengths;
    const focus = expected.focusId === 'general'
      ? { categories: [...new Set(expected.applicableFocusIds.flatMap(id => registry.focuses.find(f => f.id === id).categories))] }
      : registry.focuses.find(focus => focus.id === expected.focusId);
    for (const [findingIndex, finding] of report.findings.entries()) {
      const error = locationError(finding, focus, files, hunks);
      if (error) { lane.errors.push(`Finding ${findingIndex}: ${error}`); continue; }
      candidates.push({ focusId: expected.focusId, invocationId: expected.invocationId, runId: row.runId,
        findingIndex, finding, partial });
    }
    lane.complete = lane.errors.length === 0;
  }
  if (usedResults.size !== input.results.length) blockers.push('Unexpected runtime results');

  const decisions = new Map();
  const invalidDecisions = new Set();
  for (const decision of input.evidenceDecisions || []) {
    const key = keyOf(decision?.runId, decision?.findingIndex);
    if (!decision || !['accept', 'reject'].includes(decision.decision) || !text(decision.reason) ||
      !candidates.some(row => keyOf(row.runId, row.findingIndex) === key) || decisions.has(key)) {
      blockers.push('Unknown, duplicate or malformed evidence decision'); invalidDecisions.add(key);
    } else decisions.set(key, decision);
  }
  const accepted = [];
  const rejected = [];
  for (const candidate of candidates) {
    const key = keyOf(candidate.runId, candidate.findingIndex);
    const decision = invalidDecisions.has(key) ? null : decisions.get(key);
    if (!decision) {
      const lane = lanes.find(lane => lane.invocationId === candidate.invocationId);
      lane.complete = false;
      lane.errors.push(`Finding ${candidate.findingIndex} awaits parent evidence validation`);
    } else if (decision.decision === 'accept') accepted.push({ ...candidate, evidenceReason: decision.reason });
    else rejected.push({ ...candidate, reason: decision.reason });
  }
  const findings = mergeFindings(accepted);
  const completed = lanes.filter(lane => lane.complete).length;
  const incomplete = blockers.length > 0 || completed !== input.expected.length;
  return {
    verdict: findings.some(finding => ['critical', 'important'].includes(finding.severity)) ? 'Needs Work' : incomplete ? 'Inconclusive' : 'Passes Review',
    coverage: incomplete ? 'incomplete' : 'complete',
    counts: { selected: input.expected.length, dispatched: lanes.filter(lane => lane.dispatched).length, completed, inconclusive: input.expected.length - completed },
    blockers, lanes, candidates, findings, rejected,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    const [command, file, ...extra] = process.argv.slice(2);
    if (!['select', 'reconcile'].includes(command) || !file || extra.length) throw new Error('Usage: node validate.mjs select|reconcile <input.json>');
    const input = JSON.parse(readFileSync(file, 'utf8'));
    const result = command === 'select' ? selectFocuses(registry, input.changed_files, input.filter ?? null) : await validateReviewBundle(input);
    console.log(JSON.stringify(result, null, 2));
    if (command === 'reconcile' && result.verdict !== 'Passes Review') process.exitCode = 1;
  } catch (error) {
    console.error(JSON.stringify({ verdict: 'Inconclusive', error: error.message }));
    process.exitCode = 2;
  }
}
