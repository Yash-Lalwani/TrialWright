// One function per endpoint in CONTRACTS.md §4. Screens call only these.
//
// NEXT_PUBLIC_USE_MOCKS=false  -> real backend at NEXT_PUBLIC_API_URL (routes under /api)
// anything else (or unset)     -> frontend/mocks/*.json via lib/mock-server.ts
//
// Switching modes needs no code changes, only the env flag.

import { mock, MockNotFound } from "./mock-server";
import type {
  ApiErrorBody,
  Benchmark,
  Brief,
  Burden,
  Completeness,
  CreateDraftResponse,
  CreateRunRequest,
  CreateRunResponse,
  DecisionRequest,
  DecisionResponse,
  Draft,
  DraftProgressEvent,
  ExportFormat,
  Health,
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
  Trace,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

/** Error carrying the contract error body: {"error": {"code", "message"}}. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const api = (path: string) => `${API_URL}/api${path}`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(api(path), init);
  } catch {
    throw new ApiError(0, "network_error", `Cannot reach the Pre-Flight API at ${API_URL}.`);
  }
  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // Non-JSON error body; fall through to the status text.
    }
    throw new ApiError(
      response.status,
      body?.error?.code ?? "http_error",
      body?.error?.message ?? `${response.status} ${response.statusText}`,
    );
  }
  return (await response.json()) as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

/** Run a mock call, translating mock misses into the same ApiError the backend would give. */
async function mocked<T>(call: () => Promise<T>): Promise<T> {
  try {
    return await call();
  } catch (error) {
    if (error instanceof MockNotFound) throw new ApiError(404, "not_found", error.message);
    throw error;
  }
}

function query(filters: object): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, String(value));
  const s = params.toString();
  return s ? `?${s}` : "";
}

// ---------- 4.1 Health ----------

export const getHealth = (): Promise<Health> => (USE_MOCKS ? mocked(mock.health) : request("/health"));

// ---------- 4.2 Protocols ----------

let fallbackWorkspace: string | undefined;

/** A random id this browser keeps, so its uploads stay out of other people's lists. Privacy, not authentication. */
function workspaceHeader(): Record<string, string> {
  let id: string | null = null;
  try {
    id = window.localStorage.getItem("preflight-workspace");
    if (!id) {
      id = crypto.randomUUID();
      window.localStorage.setItem("preflight-workspace", id);
    }
  } catch {
    id = fallbackWorkspace ??= crypto.randomUUID();
  }
  return { "X-Workspace": id };
}

export const listProtocols = (): Promise<ProtocolList> =>
  USE_MOCKS ? mocked(mock.listProtocols) : request("/protocols", { headers: workspaceHeader() });

export function uploadProtocol(file: File, nctId?: string): Promise<Protocol> {
  if (USE_MOCKS) return mocked(mock.uploadProtocol);
  const form = new FormData();
  form.append("file", file);
  if (nctId) form.append("nct_id", nctId);
  return request("/protocols", { method: "POST", body: form, headers: workspaceHeader() });
}

export const protocolPdfUrl = (protocolId: string): string =>
  USE_MOCKS ? mock.pdfUrl() : api(`/protocols/${encodeURIComponent(protocolId)}/pdf`);

// ---------- 4.3 Runs ----------

export const createRun = (protocolId: string, body: CreateRunRequest): Promise<CreateRunResponse> =>
  USE_MOCKS
    ? mocked(() => mock.createRun(protocolId, body.mode))
    : request(`/protocols/${encodeURIComponent(protocolId)}/runs`, json(body));

export const getRun = (runId: string): Promise<Run> =>
  USE_MOCKS ? mocked(() => mock.getRun(runId)) : request(`/runs/${encodeURIComponent(runId)}`);

export const listProtocolRuns = (protocolId: string): Promise<RunList> =>
  USE_MOCKS
    ? mocked(() => mock.listProtocolRuns(protocolId))
    : request(`/protocols/${encodeURIComponent(protocolId)}/runs`);

export interface StreamHandlers<P> {
  onProgress: (event: P) => void;
  onComplete: (id: string) => void;
  onError: (message: string) => void;
}

/**
 * Subscribe to GET /api/{kind}/{id}/events. Returns an unsubscribe function.
 * The server's own `event: error` carries data; a bare error event is a lost connection.
 */
function subscribe<P>(path: string, idKey: "run_id" | "draft_id", handlers: StreamHandlers<P>): () => void {
  const source = new EventSource(api(path));
  source.addEventListener("progress", (e) => handlers.onProgress(JSON.parse((e as MessageEvent).data) as P));
  source.addEventListener("complete", (e) => {
    const data = JSON.parse((e as MessageEvent).data) as Record<string, string>;
    source.close();
    handlers.onComplete(data[idKey]);
  });
  source.addEventListener("error", (e) => {
    const data = (e as MessageEvent).data;
    source.close();
    handlers.onError(data ? (JSON.parse(data) as { message: string }).message : "Lost connection to the progress stream.");
  });
  return () => source.close();
}

export const subscribeRunEvents = (runId: string, handlers: StreamHandlers<ProgressEvent>): (() => void) =>
  USE_MOCKS
    ? mock.replayRunEvents(runId, handlers)
    : subscribe(`/runs/${encodeURIComponent(runId)}/events`, "run_id", handlers);

// ---------- 4.4 Issues ----------

export const listIssues = (runId: string, filters: IssueFilters = {}): Promise<IssueList> =>
  USE_MOCKS
    ? mocked(() => mock.listIssues(runId, filters))
    : request(`/runs/${encodeURIComponent(runId)}/issues${query(filters)}`);

export const decideIssue = (issueId: string, body: DecisionRequest): Promise<DecisionResponse> =>
  USE_MOCKS
    ? mocked(() => mock.decideIssue(issueId, body))
    : request(`/issues/${encodeURIComponent(issueId)}/decision`, json(body));

// ---------- 4.5 Completeness ----------

export const getCompleteness = (runId: string): Promise<Completeness> =>
  USE_MOCKS ? mocked(() => mock.getCompleteness(runId)) : request(`/runs/${encodeURIComponent(runId)}/completeness`);

// ---------- 4.6 Diff ----------

export const getDiff = (fromRunId: string, toRunId: string): Promise<RunDiff> =>
  USE_MOCKS
    ? mocked(mock.getDiff)
    : request(`/runs/${encodeURIComponent(fromRunId)}/diff/${encodeURIComponent(toRunId)}`);

// ---------- 4.7 Exports and trace ----------

/** Direct download URL. Exports are produced by the backend only; null in mock mode. */
export const exportUrl = (runId: string, format: ExportFormat): string | null =>
  USE_MOCKS ? null : api(`/runs/${encodeURIComponent(runId)}/export?format=${format}`);

export const getTrace = (runId: string): Promise<Trace> =>
  USE_MOCKS ? mocked(() => mock.getTrace(runId)) : request(`/runs/${encodeURIComponent(runId)}/trace`);

// ---------- 4.8–4.10 Burden, peers, precedent ----------

export const getBurden = (runId: string): Promise<Burden> =>
  USE_MOCKS ? mocked(mock.getBurden) : request(`/runs/${encodeURIComponent(runId)}/burden`);

export const getPeers = (runId: string): Promise<Peers> =>
  USE_MOCKS ? mocked(mock.getPeers) : request(`/runs/${encodeURIComponent(runId)}/peers`);

export const getPrecedent = (runId: string): Promise<Precedent> =>
  USE_MOCKS ? mocked(mock.getPrecedent) : request(`/runs/${encodeURIComponent(runId)}/precedent`);

// ---------- 4.11 Drafts ----------

export const createDraft = (brief: Brief): Promise<CreateDraftResponse> =>
  USE_MOCKS ? mocked(mock.createDraft) : request("/drafts", json(brief));

export const subscribeDraftEvents = (
  draftId: string,
  handlers: StreamHandlers<DraftProgressEvent>,
): (() => void) =>
  USE_MOCKS
    ? mock.replayDraftEvents(draftId, handlers)
    : subscribe(`/drafts/${encodeURIComponent(draftId)}/events`, "draft_id", handlers);

export const getDraft = (draftId: string): Promise<Draft> =>
  USE_MOCKS ? mocked(mock.getDraft) : request(`/drafts/${encodeURIComponent(draftId)}`);

export const draftExportUrl = (draftId: string, format: "usdm" | "docx"): string | null =>
  USE_MOCKS ? null : api(`/drafts/${encodeURIComponent(draftId)}/export?format=${format}`);

// ---------- 4.12 Benchmark ----------

export const getBenchmark = (): Promise<Benchmark> =>
  USE_MOCKS ? mocked(mock.getBenchmark) : request("/benchmark");
