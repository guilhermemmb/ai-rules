import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

function prompt(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8');
}

const reviewer = prompt('../pi-config/agents/reviewer.md');
const correctness = prompt('../pi-config/skills/review-pipeline/focuses/correctness.md');
const security = prompt('../pi-config/skills/review-pipeline/focuses/security.md');
const maintainability = prompt('../pi-config/skills/review-pipeline/focuses/maintainability.md');
const simplicity = prompt('../pi-config/skills/review-pipeline/focuses/simplicity.md');
const performance = prompt('../pi-config/skills/review-pipeline/focuses/performance.md');

function includesAll(text, expressions) {
  for (const expression of expressions) assert.match(text, expression);
}

test('shared reviewer guidance requires Maia-style verified, high-signal findings', () => {
  includesAll(reviewer, [
    /complete (?:supplied )?(?:diff|evidence)/i,
    /(?:callers?|contracts?|input-to-impact)/i,
    /pre-existing/i,
    /intentional/i,
    /mechanically (?:enforced|caught)/i,
    /speculat(?:e|ion|ive)/i,
    /pedantry|pedantic/i,
    /report-only/i,
    /parent .*verdict|parent computes the verdict/i,
  ]);
});

test('correctness guidance covers silent failures and conditional migration safety', () => {
  includesAll(correctness, [
    /catch-and-continue|swallowed asynchronous errors|fallbacks? .*erase failures/i,
    /migrations?|query builders?|planner-sensitive/i,
    /data loss|heavy locks|table rewrites?/i,
    /deployment|execution consequence/i,
    /query plans? .*trivial|trivial .*query plans?/i,
  ]);
});

test('security guidance covers modern trust-boundary and dependency-update risks', () => {
  includesAll(security, [
    /insecure direct object access|privilege escalation/i,
    /SSRF/i,
    /path traversal/i,
    /open redirects?/i,
    /dependency (?:versions?|updates?)/i,
    /release|advisory/i,
    /repository (?:usage|use)|actual usage/i,
  ]);
});

test('maintainability guidance requires concrete behavioral tests and accurate documentation', () => {
  includesAll(maintainability, [
    /named changed (?:behavior|implementation)|concrete (?:error path|boundary|negative case)/i,
    /assertions? .*contract|tests? .*assert/i,
    /comments?, docstrings?, examples?/i,
    /missing rationale|non-obvious invariant|side effect/i,
    /numeric coverage|universal tests?/i,
  ]);
});

test('simplicity and performance guidance require evidence-led alternatives', () => {
  includesAll(simplicity, [
    /existing (?:helper|implementation|mechanism)/i,
    /derivable state|deep nesting|special case/i,
    /simpler alternative|behavior-preserving/i,
    /taste-only|subjective/i,
  ]);
  includesAll(performance, [
    /(?:hot path|workload bounds?|resource bounds?)/i,
    /I\/O|computation/i,
    /behavior-changing|subjective/i,
  ]);
});
