import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { pathToFileURL } from "node:url";
import test from "node:test";

const workflowUrl = new URL("../pi-config/workflows/pi-review.js", import.meta.url);
const runtimeRoot = process.env.PI_DYNAMIC_WORKFLOWS_ROOT
  ?? join(tmpdir(), "pi-dynamic-workflows-3.13.1", "node_modules", "@quintinshaw", "pi-dynamic-workflows");

async function loadRuntime() {
  const packageJson = JSON.parse(await readFile(join(runtimeRoot, "package.json"), "utf8"));
  assert.equal(packageJson.version, "3.13.1");
  return import(pathToFileURL(join(runtimeRoot, "dist", "index.js")));
}

function workflowArgs(focusIds = ["correctness", "git-safety"]) {
  return {
    version: 1,
    repo: "/tmp/review-fixture",
    cwd: "/tmp/review-fixture",
    scope: { mode: "current" },
    packetRef: "/tmp/review-fixture/packet.json",
    packetDigest: `sha256:${"a".repeat(64)}`,
    selected: focusIds.map((focusId, index) => ({
      focusId,
      invocationId: `focus-${index + 1}`,
      fileIds: ["file-1"],
      hunkIds: ["hunk-1"],
    })),
    excluded: [],
  };
}

function completeReview(findings = []) {
  return {
    status: "complete",
    coverage: {
      status: "complete",
      fileIds: ["file-1"],
      hunkIds: ["hunk-1"],
      limitations: [],
    },
    findings,
    errors: [],
  };
}

function fakeReviewer(calls, respond) {
  return {
    async run(prompt, options = {}) {
      calls.push({ prompt, options });
      if (respond) return respond(prompt, options);
      if (prompt.startsWith("REVIEW FOCUS")) return completeReview();
      if (prompt.startsWith("VERIFY FOCUS")) {
        return { status: "complete", candidates: [], errors: [] };
      }
      return "# Review report\n\nNo validated findings.";
    },
  };
}

async function execute(args, { respond, maxAgents = args.selected.length * 2 + 1, events, journal } = {}) {
  const { runWorkflow } = await loadRuntime();
  const source = await readFile(workflowUrl, "utf8");
  const calls = [];
  const result = await runWorkflow(source, {
    args,
    agent: fakeReviewer(calls, respond),
    agentRegistry: reviewerRegistry,
    concurrency: 4,
    maxAgents,
    persistLogs: false,
    runId: "test-pi-review",
    resumeJournal: journal,
    onAgentJournal: events ? (entry) => events.journal.push(entry) : undefined,
    onAgentStart: events ? (event) => events.starts.push(event) : undefined,
  });
  return { result, calls };
}

const reviewerRegistry = new Map([
  ["reviewer", {
    name: "reviewer",
    description: "Read-only review agent",
    tools: ["read", "bash"],
    model: "openai-codex/gpt-5.6-terra",
    thinking: "medium",
    prompt: "Review only the assigned frozen evidence.",
    source: "user",
  }],
]);

async function loadRegistry() {
  const source = await readFile(workflowUrl, "utf8");
  const match = source.match(
    /\/\* registry:start \*\/\s*([\s\S]*?)\s*\/\* registry:end \*\//,
  );
  assert.ok(match, "workflow must expose its VM-local registry between contract markers");
  return Function(`"use strict"; return (${match[1]});`)();
}

test("canonical registry merges React guidance into Performance", async () => {
  const registry = await loadRegistry();
  assert.deepEqual(
    registry.map(({ id }) => id),
    [
      "general",
      "correctness",
      "simplicity",
      "accessibility",
      "security",
      "performance",
      "maintainability",
      "design-consistency",
      "git-safety",
    ],
  );
  assert.equal(registry.some(({ id }) => id === "react-best-practices"), false);

  const performance = registry.find(({ id }) => id === "performance");
  assert.deepEqual(performance.categories, [
    "n-plus-one",
    "algorithm",
    "memory",
    "rendering",
    "bundle",
    "io",
    "blocking",
    "async",
    "server",
    "client",
    "rerender",
    "js",
    "advanced",
  ]);
  assert.match(performance.prompt, /Algorithmic growth on realistic input sizes/);
  assert.match(performance.reactPrompt, /pinned `vercel-react-best-practices`/);
  assert.match(performance.reactPrompt, /real rule filename/);
});

test("canonical registry preserves every non-React focus contract", async () => {
  const registry = await loadRegistry();
  const expected = {
    general: ["complete frozen evidence", "applicable focuses"],
    correctness: ["Async ordering", "query-plan evidence", "null-safety"],
    simplicity: ["behavior-preserving simpler alternative", "over-abstraction"],
    accessibility: ["dialog focus restoration", "assistive-technology validation"],
    security: ["attacker-controlled input", "dependency vulnerabilities"],
    maintainability: ["concrete error path", "tests tied to implementation detail"],
    "design-consistency": ["existing token", "personal aesthetic preferences"],
    "git-safety": ["credential-bearing URLs", "side: \"file\""],
  };

  for (const [id, phrases] of Object.entries(expected)) {
    const focus = registry.find((entry) => entry.id === id);
    assert.ok(focus, `missing ${id}`);
    for (const phrase of phrases) assert.match(focus.prompt, new RegExp(phrase));
  }
});

test("workflow runs ordered review, verify, and report barriers through reviewer", async () => {
  const { parseWorkflowScript, runWorkflow } = await loadRuntime();
  const source = await readFile(workflowUrl, "utf8");
  const parsed = parseWorkflowScript(source);
  assert.deepEqual(parsed.meta.phases.map(({ title }) => title), ["Review", "Verify", "Report"]);

  const calls = [];
  const phases = [];
  const result = await runWorkflow(source, {
    args: workflowArgs(),
    agent: fakeReviewer(calls),
    agentRegistry: reviewerRegistry,
    concurrency: 4,
    maxAgents: 5,
    persistLogs: false,
    onPhase: (title) => phases.push(title),
  });

  assert.deepEqual(phases, ["Review", "Verify", "Report"]);
  assert.equal(calls.length, 5);
  assert.deepEqual(
    calls.map(({ prompt }) => prompt.split("\n", 1)[0]),
    [
      "REVIEW FOCUS correctness",
      "REVIEW FOCUS git-safety",
      "VERIFY FOCUS correctness",
      "VERIFY FOCUS git-safety",
      "SYNTHESIZE REVIEW",
    ],
  );
  assert.ok(calls.every(({ options }) => options.model === "openai-codex/gpt-5.6-terra"));
  assert.ok(calls.every(({ options }) => options.thinking === "medium"));
  assert.equal(result.agentCount, 5);
  assert.doesNotThrow(() => JSON.stringify(result.result));
  assert.equal(result.result.verdict, "Passes Review");
  assert.equal(result.result.coverage, "complete");
});

test("single general review receives the applicable focus taxonomy", async () => {
  const args = workflowArgs(["general"]);
  args.selected[0].applicableFocusIds = ["correctness", "security"];
  const { calls } = await execute(args);
  assert.match(calls[0].prompt, /Applicable focus IDs: \["correctness","security"\]/);
  assert.match(calls[0].prompt, /"logic"/);
  assert.match(calls[0].prompt, /"injection"/);
});

test("one missing review remains visible and cannot become a pass", async () => {
  const { result, calls } = await execute(workflowArgs(), {
    respond(prompt) {
      if (prompt === undefined) throw new Error("missing prompt");
      if (prompt.startsWith("REVIEW FOCUS correctness")) return null;
      if (prompt.startsWith("REVIEW FOCUS")) return completeReview();
      if (prompt.startsWith("VERIFY FOCUS")) return { status: "complete", candidates: [], errors: [] };
      return "# Inconclusive review";
    },
  });

  assert.equal(calls.length, 4);
  assert.equal(result.result.verdict, "Inconclusive");
  assert.equal(result.result.coverage, "incomplete");
  assert.equal(result.result.completed, 1);
  assert.equal(result.result.inconclusive, 1);
  assert.equal(result.result.focuses[0].review, null);
});

test("missing verifier leaves candidates unverified and coverage incomplete", async () => {
  const finding = {
    candidateId: "candidate-1",
    severity: "minor",
    category: "logic",
    fileId: "file-1",
    hunkId: "hunk-1",
    title: "Candidate",
    evidence: "Changed branch returns the wrong value.",
    impact: "The caller observes a wrong result.",
    fix: "Restore the expected branch.",
  };
  const { result } = await execute(workflowArgs(["correctness"]), {
    respond(prompt) {
      if (prompt.startsWith("REVIEW FOCUS")) return completeReview([finding]);
      if (prompt.startsWith("VERIFY FOCUS")) return null;
      return "# Inconclusive review";
    },
  });

  assert.equal(result.result.verdict, "Inconclusive");
  assert.equal(result.result.coverage, "incomplete");
  assert.equal(result.result.findings.length, 0);
});

test("validated important findings take precedence over incomplete coverage", async () => {
  const finding = {
    candidateId: "candidate-1",
    severity: "important",
    category: "logic",
    fileId: "file-1",
    hunkId: "hunk-1",
    title: "Reachable regression",
    evidence: "Changed branch returns the wrong value.",
    impact: "Every caller observes a wrong result.",
    fix: "Restore the expected branch.",
  };
  const { result } = await execute(workflowArgs(), {
    respond(prompt) {
      if (prompt.startsWith("REVIEW FOCUS correctness")) return completeReview([finding]);
      if (prompt.startsWith("REVIEW FOCUS git-safety")) return null;
      if (prompt.startsWith("VERIFY FOCUS correctness")) {
        return {
          status: "complete",
          candidates: [{ candidateId: "candidate-1", accepted: true, reason: "Reproduced from frozen evidence", rootCauseId: "root-1" }],
          errors: [],
        };
      }
      return "# Needs Work";
    },
  });

  assert.equal(result.result.verdict, "Needs Work");
  assert.equal(result.result.coverage, "incomplete");
  assert.equal(result.result.findings.length, 1);
  assert.equal(result.result.findings[0].focusId, "correctness");
  assert.equal(result.result.findings[0].verificationReason, "Reproduced from frozen evidence");
});

test("tampered React overlay keeps Performance selected but incomplete", async () => {
  const args = workflowArgs(["performance"]);
  args.reactOverlay = {
    applicable: true,
    skillRoot: "/tmp/vercel-react-best-practices",
    revision: "pinned-revision",
    ruleIds: ["async-parallel"],
    integrityError: "rule inventory digest mismatch",
  };
  const { result, calls } = await execute(args);

  assert.equal(result.result.focuses[0].focusId, "performance");
  assert.equal(result.result.focuses[0].overlayIncomplete, true);
  assert.equal(result.result.verdict, "Inconclusive");
  assert.match(calls[0].prompt, /rule inventory digest mismatch/);
});

test("runtime enforces the exact 2N+1 logical-agent ceiling", async () => {
  await assert.rejects(
    execute(workflowArgs(), { maxAgents: 4 }),
    /maximum agent limit|agent limit|maxAgents/i,
  );
});

test("canonical focus ordering yields stable unique call labels", async () => {
  const args = workflowArgs(["git-safety", "correctness"]);
  const events = { starts: [], journal: [] };
  await execute(args, { events });
  const labels = events.starts.map(({ label }) => label);
  assert.equal(new Set(labels).size, labels.length);
  assert.deepEqual(labels, [
    "review:0:correctness",
    "review:1:git-safety",
    "verify:0:correctness",
    "verify:1:git-safety",
    "report:final",
  ]);
});

test("journal resume replays only the unchanged successful positional prefix", async () => {
  const args = workflowArgs();
  const firstEvents = { starts: [], journal: [] };
  await execute(args, { events: firstEvents });
  assert.equal(firstEvents.journal.length, 5);

  const journal = new Map(firstEvents.journal.map((entry) => [
    `${entry.runId ?? "test-pi-review"}:${entry.index}`,
    entry,
  ]));
  journal.delete("test-pi-review:2");
  const resumedEvents = { starts: [], journal: [] };
  const { calls } = await execute(args, { events: resumedEvents, journal });

  assert.equal(calls.length, 3);
  assert.deepEqual(
    resumedEvents.starts.map(({ replayed }) => replayed === true),
    [true, true, false, false, false],
  );
});

test("validated findings are not capped during aggregation or synthesis", async () => {
  const findings = Array.from({ length: 12 }, (_, index) => ({
    candidateId: `candidate-${index + 1}`,
    severity: "minor",
    category: "logic",
    fileId: "file-1",
    hunkId: "hunk-1",
    title: `Finding ${index + 1}`,
    evidence: `Evidence ${index + 1}`,
    impact: `Impact ${index + 1}`,
    fix: `Fix ${index + 1}`,
  }));
  const { result, calls } = await execute(workflowArgs(["correctness"]), {
    respond(prompt) {
      if (prompt.startsWith("REVIEW FOCUS")) return completeReview(findings);
      if (prompt.startsWith("VERIFY FOCUS")) {
        return {
          status: "complete",
          candidates: findings.map(({ candidateId }) => ({
            candidateId,
            accepted: true,
            reason: "Supported by frozen evidence",
            rootCauseId: `correctness:${candidateId}`,
          })),
          errors: [],
        };
      }
      return "# Review report";
    },
  });

  assert.equal(result.result.findings.length, 12);
  assert.match(calls.at(-1).prompt, /candidate-12/);
});

test("coverage requires the exact assigned file and hunk inventory", async () => {
  const { result } = await execute(workflowArgs(["correctness"]), {
    respond(prompt) {
      if (prompt.startsWith("REVIEW FOCUS")) {
        const review = completeReview();
        review.coverage.fileIds = [];
        return review;
      }
      if (prompt.startsWith("VERIFY FOCUS")) return { status: "complete", candidates: [], errors: [] };
      return "# Inconclusive";
    },
  });
  assert.equal(result.result.verdict, "Inconclusive");
  assert.equal(result.result.focuses[0].status, "inconclusive");
});

test("invalid finding anchors, categories, and React rule IDs cannot be accepted", async () => {
  const args = workflowArgs(["performance"]);
  args.reactOverlay = {
    applicable: true,
    skillRoot: "/tmp/vercel-react-best-practices",
    revision: "revision",
    ruleIds: ["async-parallel"],
  };
  const invalid = {
    candidateId: "candidate-invalid",
    severity: "important",
    category: "async",
    fileId: "not-assigned",
    hunkId: "hunk-1",
    title: "Invalid evidence",
    evidence: "Not anchored to the assignment.",
    impact: "Cannot be established.",
    fix: "None.",
    ruleId: "not-a-real-rule",
  };
  const { result } = await execute(args, {
    respond(prompt) {
      if (prompt.startsWith("REVIEW FOCUS")) return completeReview([invalid]);
      if (prompt.startsWith("VERIFY FOCUS")) return {
        status: "complete",
        candidates: [{ candidateId: invalid.candidateId, accepted: true, reason: "claimed" }],
        errors: [],
      };
      return "# Inconclusive";
    },
  });
  assert.equal(result.result.verdict, "Inconclusive");
  assert.equal(result.result.findings.length, 0);
});

test("deduplication keeps the highest severity and all cross-focus provenance", async () => {
  const findings = {
    correctness: {
      candidateId: "correctness-1", severity: "minor", category: "logic", fileId: "file-1", hunkId: "hunk-1",
      title: "Minor view", evidence: "Same root cause.", impact: "Small impact.", fix: "Shared fix.",
    },
    security: {
      candidateId: "security-1", severity: "important", category: "input-validation", fileId: "file-1", hunkId: "hunk-1",
      title: "Important view", evidence: "Same root cause.", impact: "Reachable security impact.", fix: "Shared fix.",
    },
  };
  const verificationPrompts = [];
  const { result } = await execute(workflowArgs(["correctness", "security"]), {
    respond(prompt) {
      if (prompt.startsWith("REVIEW FOCUS correctness")) return completeReview([findings.correctness]);
      if (prompt.startsWith("REVIEW FOCUS security")) return completeReview([findings.security]);
      if (prompt.startsWith("VERIFY FOCUS")) verificationPrompts.push(prompt);
      if (prompt.startsWith("VERIFY FOCUS correctness")) return {
        status: "complete", candidates: [{ candidateId: "correctness-1", accepted: true, reason: "supported", rootCauseId: "shared-root" }], errors: [],
      };
      if (prompt.startsWith("VERIFY FOCUS security")) return {
        status: "complete", candidates: [{ candidateId: "security-1", accepted: true, reason: "supported", rootCauseId: "shared-root" }], errors: [],
      };
      return "# Needs Work";
    },
  });
  assert.equal(result.result.findings.length, 1);
  assert.equal(result.result.findings[0].severity, "important");
  assert.equal(result.result.findings[0].provenance.length, 2);
  assert.equal(verificationPrompts.length, 2);
  for (const prompt of verificationPrompts) {
    assert.match(prompt, /Full producer ledger/);
    assert.match(prompt, /correctness-1/);
    assert.match(prompt, /security-1/);
    assert.match(prompt, /lexicographically smallest/i);
  }
});

test("accepted decisions without a canonical root cause stay inconclusive", async () => {
  const finding = {
    candidateId: "candidate-no-root", severity: "important", category: "logic", fileId: "file-1", hunkId: "hunk-1",
    title: "Supported issue", evidence: "Frozen evidence.", impact: "Reachable impact.", fix: "Small fix.",
  };
  const { result } = await execute(workflowArgs(["correctness"]), {
    respond(prompt) {
      if (prompt.startsWith("REVIEW FOCUS")) return completeReview([finding]);
      if (prompt.startsWith("VERIFY FOCUS")) return {
        status: "complete",
        candidates: [{ candidateId: finding.candidateId, accepted: true, reason: "supported" }],
        errors: [],
      };
      return "# Inconclusive";
    },
  });
  assert.equal(result.result.verdict, "Inconclusive");
  assert.equal(result.result.findings.length, 0);
});

test("duplicate candidate IDs cannot share one verifier decision", async () => {
  const duplicate = (title) => ({
    candidateId: "duplicate-id", severity: "important", category: "logic", fileId: "file-1", hunkId: "hunk-1",
    title, evidence: "Ambiguous candidate evidence.", impact: "Cannot map verification safely.", fix: "Use unique IDs.",
  });
  const { result } = await execute(workflowArgs(["correctness"]), {
    respond(prompt) {
      if (prompt.startsWith("REVIEW FOCUS")) return completeReview([duplicate("First"), duplicate("Second")]);
      if (prompt.startsWith("VERIFY FOCUS")) return {
        status: "complete",
        candidates: [{ candidateId: "duplicate-id", accepted: true, reason: "ambiguous", rootCauseId: "shared" }],
        errors: [],
      };
      return "# Inconclusive";
    },
  });
  assert.equal(result.result.verdict, "Inconclusive");
  assert.equal(result.result.findings.length, 0);
});

test("malformed structured review output fails visibly", async () => {
  await assert.rejects(
    execute(workflowArgs(["correctness"]), {
      respond(prompt) {
        if (prompt.startsWith("REVIEW FOCUS")) return {};
        return null;
      },
    }),
    /coverage|status|findings|undefined/i,
  );
});

test("malformed packet identity fails before any reviewer call", async () => {
  const args = workflowArgs(["correctness"]);
  delete args.packetRef;
  await assert.rejects(execute(args), /Invalid packetRef/);
});

test("missing final synthesis cannot yield a passing verdict", async () => {
  const { result } = await execute(workflowArgs(["correctness"]), {
    respond(prompt) {
      if (prompt.startsWith("REVIEW FOCUS")) return completeReview();
      if (prompt.startsWith("VERIFY FOCUS")) return { status: "complete", candidates: [], errors: [] };
      return null;
    },
  });
  assert.equal(result.result.report, null);
  assert.equal(result.result.verdict, "Inconclusive");
});

test("a missing reviewer route cannot yield a clean review", async () => {
  const { runWorkflow } = await loadRuntime();
  const source = await readFile(workflowUrl, "utf8");
  const result = await runWorkflow(source, {
    args: workflowArgs(["correctness"]),
    agent: fakeReviewer([], (_prompt, options) => {
      if (options.model !== "openai-codex/gpt-5.6-terra") throw new Error("reviewer route unavailable");
      return completeReview();
    }),
    agentRegistry: new Map(),
    concurrency: 4,
    maxAgents: 3,
    persistLogs: false,
  });
  assert.notEqual(result.result.verdict, "Passes Review");
  assert.equal(result.result.coverage, "incomplete");
});
