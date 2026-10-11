// In-browser stand-in for the backend when NEXT_PUBLIC_USE_MOCKS is not "false".
// It serves frontend/mocks/*.json with contract shapes (CONTRACTS.md §4–5), keeps
// decisions in memory for the session, and replays SSE progress at 1 s per step.
// Mock JSON is imported lazily so it is not part of the real-API bundle path.

import type {
  Benchmark,
  Burden,
  Completeness,
  CreateDraftResponse,
  CreateRunResponse,
  DecisionRequest,
  DecisionResponse,
  Draft,
  DraftProgressEvent,
  Health,
  Issue,
  IssueCounts,
  IssueFilters,
  IssueList,
  Peers,
  Precedent,
  ProgressEvent,
  Protocol,
  ProtocolList,
  Run,
  RunDiff,
  RunList,
  RunMode,
  Trace,
} from "./types";

export class MockNotFound extends Error {}

const LATENCY_MS = 300;
export const MOCK_STEP_MS = 1000;

const wait = (ms = LATENCY_MS) => new Promise((r) => setTimeout(r, ms));
/** Deep copy of a fixture. JSON imports widen tuples (bbox) and enums, so they pass through unknown. */
const clone = <T>(value: unknown): T => structuredClone(value) as T;

/** Session state: issue decisions and the mode chosen for each mock run. */
const state = {
  issues: null as Issue[] | null,
  runModes: new Map<string, RunMode>(),
  nextAudit: 78,
  audit: [] as Trace["audit"],
};

async function allIssues(): Promise<Issue[]> {
  if (!state.issues) {
    const data = clone<IssueList>((await import("@/mocks/issues.json")).default);
    state.issues = data.items;
  }
  return state.issues;
}

/** A rules_only run has no AI reviewer findings. */
async function issuesForRun(runId: string): Promise<Issue[]> {
  const items = await allIssues();
  return state.runModes.get(runId) === "rules_only" ? items.filter((i) => i.source === "rule") : items;
}

function countIssues(items: Issue[]): IssueCounts {
  const counts: IssueCounts = { critical: 0, major: 0, minor: 0, advisory: 0, open: 0, accepted: 0, rejected: 0 };
  for (const i of items) {
    counts[i.severity] += 1;
    counts[i.status] += 1;
  }
  return counts;
}

const KNOWN_RUN = "run_31c9";
const SECOND_RUN = "run_52aa"; // v2 of the sample protocol; /compare diffs run_31c9 against it
const FAILED_RUN = "run_a802";

function assertRun(runId: string) {
  if (runId !== KNOWN_RUN && runId !== SECOND_RUN && runId !== FAILED_RUN) throw new MockNotFound(`Run ${runId} not found`);
}

export const mock = {
  async health(): Promise<Health> {
    await wait();
    return clone((await import("@/mocks/health.json")).default);
  },

  async listProtocols(): Promise<ProtocolList> {
    await wait();
    return clone((await import("@/mocks/protocols.json")).default) as ProtocolList;
  },

  /** The uploaded file stays in the browser; the synthetic sample protocol is returned. */
  async uploadProtocol(): Promise<Protocol> {
    await wait(700);
    return clone((await import("@/mocks/protocol.json")).default);
  },

  pdfUrl(): string {
    return "/sample-protocol.pdf";
  },

  async createRun(_protocolId: string, mode: RunMode): Promise<CreateRunResponse> {
    await wait();
    const created = clone((await import("@/mocks/run_create.json")).default) as CreateRunResponse;
    state.runModes.set(created.run_id, mode);
    return created;
  },

  async getRun(runId: string): Promise<Run> {
    await wait();
    assertRun(runId);
    if (runId === FAILED_RUN) return clone((await import("@/mocks/run_failed.json")).default) as Run;
    if (runId === SECOND_RUN) {
      const runs = clone((await import("@/mocks/protocol_runs.json")).default) as RunList;
      return runs.items.find((r) => r.run_id === SECOND_RUN)!;
    }
    const run = clone((await import("@/mocks/run.json")).default) as Run;
    run.mode = state.runModes.get(runId) ?? run.mode;
    run.counts = countIssues(await issuesForRun(runId));
    return run;
  },

  async listProtocolRuns(protocolId: string): Promise<RunList> {
    await wait();
    const runs = clone((await import("@/mocks/protocol_runs.json")).default) as RunList;
    return { items: runs.items.filter((r) => r.protocol_id === protocolId) };
  },

  async listIssues(runId: string, filters: IssueFilters = {}): Promise<IssueList> {
    await wait();
    assertRun(runId);
    if (runId === FAILED_RUN) return { total: 0, items: [] };
    if (runId === SECOND_RUN) {
      // v2 of the sample: what remains after the diff's resolved issues were fixed.
      const diff = clone((await import("@/mocks/diff.json")).default) as RunDiff;
      return { total: diff.unchanged.length, items: diff.unchanged };
    }
    const items = (await issuesForRun(runId)).filter((i) =>
      (Object.keys(filters) as (keyof IssueFilters)[]).every((k) => !filters[k] || i[k] === filters[k]),
    );
    return { total: items.length, items: clone(items) };
  },

  async decideIssue(issueId: string, body: DecisionRequest): Promise<DecisionResponse> {
    await wait();
    const issue = (await allIssues()).find((i) => i.id === issueId);
    if (!issue) throw new MockNotFound(`Issue ${issueId} not found`);
    issue.status = body.decision;
    const auditId = `aud_${state.nextAudit++}`;
    state.audit.push({ audit_id: auditId, issue_id: issueId, decision: body.decision, user: body.user, note: body.note, at: new Date().toISOString() });
    const example = clone((await import("@/mocks/decision.json")).default) as DecisionResponse;
    const run = (await import("@/mocks/run.json")).default as Run;
    return {
      issue_id: issueId,
      status: body.decision,
      audit_id: auditId,
      // Accepting removes the issue's points (contract example score); rejecting keeps the score.
      score: body.decision === "accepted" ? example.score : clone(run.score!),
    };
  },

  async getCompleteness(runId: string): Promise<Completeness> {
    await wait();
    assertRun(runId);
    return clone((await import("@/mocks/completeness.json")).default) as Completeness;
  },

  async getDiff(): Promise<RunDiff> {
    await wait();
    return clone((await import("@/mocks/diff.json")).default) as RunDiff;
  },

  async getTrace(runId: string): Promise<Trace> {
    await wait();
    assertRun(runId);
    const trace = clone((await import("@/mocks/trace.json")).default) as Trace;
    trace.audit = [...trace.audit, ...state.audit];
    return trace;
  },

  async getBurden(): Promise<Burden> {
    await wait();
    return clone((await import("@/mocks/burden.json")).default);
  },

  async getPeers(): Promise<Peers> {
    await wait();
    return clone((await import("@/mocks/peers.json")).default);
  },

  async getPrecedent(): Promise<Precedent> {
    await wait();
    return clone((await import("@/mocks/precedent.json")).default);
  },

  async createDraft(): Promise<CreateDraftResponse> {
    await wait();
    return clone((await import("@/mocks/draft_create.json")).default) as CreateDraftResponse;
  },

  async getDraft(): Promise<Draft> {
    await wait();
    return clone((await import("@/mocks/draft.json")).default) as Draft;
  },

  async getBenchmark(): Promise<Benchmark> {
    await wait();
    return clone((await import("@/mocks/benchmark.json")).default) as Benchmark;
  },

  /** Replays the documented step list, one event per second. Returns a cancel function. */
  replayRunEvents(
    runId: string,
    handlers: { onProgress: (e: ProgressEvent) => void; onComplete: (runId: string) => void },
  ): () => void {
    return replay(async () => {
      const script = (await import("@/mocks/run_events.json")).default;
      const rulesOnly = state.runModes.get(runId) === "rules_only";
      return (script.progress as ProgressEvent[]).map((e) =>
        rulesOnly && (e.step === "reviewers" || e.step === "verify")
          ? { ...e, status: "skipped" as const, message: script.skipped_message }
          : e,
      );
    }, handlers.onProgress, () => handlers.onComplete(runId));
  },

  replayDraftEvents(
    draftId: string,
    handlers: { onProgress: (e: DraftProgressEvent) => void; onComplete: (draftId: string) => void },
  ): () => void {
    return replay(
      async () => (await import("@/mocks/draft_events.json")).default.progress as DraftProgressEvent[],
      handlers.onProgress,
      () => handlers.onComplete(draftId),
    );
  },
};

/** Emits each event MOCK_STEP_MS apart, then calls onDone. Returns a cancel function. */
function replay<E>(load: () => Promise<E[]>, onEvent: (e: E) => void, onDone: () => void): () => void {
  let cancelled = false;
  const timers: ReturnType<typeof setTimeout>[] = [];
  void load().then((events) => {
    if (cancelled) return;
    events.forEach((event, i) => {
      timers.push(setTimeout(() => !cancelled && onEvent(event), (i + 1) * MOCK_STEP_MS));
    });
    timers.push(setTimeout(() => !cancelled && onDone(), (events.length + 1) * MOCK_STEP_MS));
  });
  return () => {
    cancelled = true;
    timers.forEach(clearTimeout);
  };
}
