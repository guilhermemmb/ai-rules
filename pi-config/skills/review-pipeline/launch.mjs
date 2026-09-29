import { randomUUID } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { isAbsolute } from 'node:path';
import { fileURLToPath } from 'node:url';

const registry = JSON.parse(readFileSync(new URL('pipeline.json', import.meta.url)));
const childOptions = schema => ({ outputSchema: schema, output: false, outputMode: 'inline',
  artifacts: true, acceptance: { level: 'attested', report: 'on' } });

export function buildReviewerLaunch({ invocation, selectedFocuses, packetRef, packetDigest, assignedIds,
  focusTexts, schema, cwd }) {
  if (!invocation || !['parallel', 'single', 'focus'].includes(invocation.mode) ||
    !Array.isArray(selectedFocuses) || !selectedFocuses.length ||
    !isAbsolute(packetRef ?? '') || !isAbsolute(cwd ?? '') || !/^sha256:[a-f0-9]{64}$/.test(packetDigest ?? '') ||
    !Array.isArray(assignedIds?.files) || !Array.isArray(assignedIds?.hunks) || schema?.type !== 'object') {
    throw new Error('Invalid reviewer launch inputs or evidence identity');
  }
  const ids = invocation.mode === 'single' ? ['general'] : invocation.mode === 'focus'
    ? [invocation.focusId] : selectedFocuses.map(row => row.id);
  if (new Set(ids).size !== ids.length || ids.some(id => id !== 'general' && !registry.focuses.some(f => f.id === id)) ||
    ids.some(id => typeof focusTexts?.[id] !== 'string' || !focusTexts[id].trim())) throw new Error('Invalid focus instructions');
  const expected = ids.map(focusId => ({ focusId, invocationId: randomUUID(),
    ...(focusId === 'general' ? { applicableFocusIds: selectedFocuses.map(row => row.id) } : {}) }));
  const lanes = expected.map(row => ({ focusId: row.focusId, invocationId: row.invocationId,
    task: `Report-only AI review (${row.focusId}). ${focusTexts[row.focusId]}\n` +
      `Read ${fileURLToPath(new URL('contracts.md', import.meta.url))} and the complete frozen evidence at ${packetRef}.\n` +
      `Repository: ${cwd}. Scope: ${invocation.scope}${invocation.prUrl ? `, PR: ${invocation.prUrl}` : ''}.\n` +
      `Assigned file IDs: ${JSON.stringify(assignedIds.files)}; hunk IDs: ${JSON.stringify(assignedIds.hunks)}.\n` +
      `Return the structured report only. Use focus_id=${row.focusId}, invocation_id=${row.invocationId}, packet_digest=${packetDigest}.\n` +
      'Submit structured_output with {value: <schema-valid report>, acceptanceReport: <runtime evidence>}.' }));
  if (invocation.mode !== 'parallel') return { kind: 'direct', expected, subagentArgs: {
    agent: 'reviewer', task: lanes[0].task, cwd, async: true, context: 'fresh', ...childOptions(schema),
  } };
  const maxConcurrency = registry.max_concurrent_reviewers;
  if (!Number.isInteger(maxConcurrency) || maxConcurrency < 1 || maxConcurrency > 4) throw new Error('Invalid registry concurrency');
  return { kind: 'workflow', expected, subagentArgs: {
    workflowScriptPath: fileURLToPath(new URL('dispatch.js', import.meta.url)),
    args: { maxConcurrency, packetDigest, reportSchema: schema, lanes },
    cwd, async: true, context: 'fresh', outputMode: 'inline', artifacts: true,
    globalConcurrencyLimit: maxConcurrency,
  } };
}
