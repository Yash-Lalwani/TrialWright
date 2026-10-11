// TanStack Query hooks over lib/api.ts. Keys are shared so mutations can update caches.

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "./api";
import type { DecisionRequest, DecisionResponse, Issue, IssueCounts, IssueList, Run } from "./types";

export const keys = {
  health: ["health"] as const,
  protocols: ["protocols"] as const,
  run: (runId: string) => ["run", runId] as const,
  issues: (runId: string) => ["issues", runId] as const,
  completeness: (runId: string) => ["completeness", runId] as const,
  trace: (runId: string) => ["trace", runId] as const,
  burden: (runId: string) => ["burden", runId] as const,
  peers: (runId: string) => ["peers", runId] as const,
  precedent: (runId: string) => ["precedent", runId] as const,
  protocolRuns: (protocolId: string) => ["protocol-runs", protocolId] as const,
  diff: (from: string, to: string) => ["diff", from, to] as const,
  benchmark: ["benchmark"] as const,
};

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.getHealth, retry: false });

export const useProtocols = () => useQuery({ queryKey: keys.protocols, queryFn: api.listProtocols });

export const useRun = (runId: string) => useQuery({ queryKey: keys.run(runId), queryFn: () => api.getRun(runId) });

/** All issues for a run; the workspace filters client-side so counts stay visible per filter. */
export const useIssues = (runId: string, enabled = true) =>
  useQuery({ queryKey: keys.issues(runId), queryFn: () => api.listIssues(runId), enabled });

export const useCompleteness = (runId: string, enabled = true) =>
  useQuery({ queryKey: keys.completeness(runId), queryFn: () => api.getCompleteness(runId), enabled });

export const useTrace = (runId: string, enabled = true) =>
  useQuery({ queryKey: keys.trace(runId), queryFn: () => api.getTrace(runId), enabled });

// B's endpoints answer 409 (no graph yet) and 404 (no peer set / benchmark); retrying cannot fix those.
const noRetryOnClientError = (count: number, error: Error) =>
  !(error instanceof api.ApiError && error.status >= 400 && error.status < 500) && count < 2;

export const useBurden = (runId: string) =>
  useQuery({ queryKey: keys.burden(runId), queryFn: () => api.getBurden(runId), retry: noRetryOnClientError });

export const usePeers = (runId: string) =>
  useQuery({ queryKey: keys.peers(runId), queryFn: () => api.getPeers(runId), retry: noRetryOnClientError });

export const usePrecedent = (runId: string) =>
  useQuery({ queryKey: keys.precedent(runId), queryFn: () => api.getPrecedent(runId), retry: noRetryOnClientError });

export const useBenchmark = () =>
  useQuery({ queryKey: keys.benchmark, queryFn: api.getBenchmark, retry: noRetryOnClientError });

export const useProtocolRuns = (protocolId: string | undefined) =>
  useQuery({
    queryKey: keys.protocolRuns(protocolId ?? ""),
    queryFn: () => api.listProtocolRuns(protocolId!),
    enabled: !!protocolId,
  });

export const useDiff = (from: string | null, to: string | null) =>
  useQuery({ queryKey: keys.diff(from ?? "", to ?? ""), queryFn: () => api.getDiff(from!, to!), enabled: !!from && !!to && from !== to });

function countIssues(items: Issue[], previous: IssueCounts | null): IssueCounts {
  const counts: IssueCounts = { critical: 0, major: 0, minor: 0, advisory: 0, open: 0, accepted: 0, rejected: 0 };
  for (const i of items) {
    counts[i.severity] += 1;
    counts[i.status] += 1;
  }
  return previous ? { ...previous, ...counts } : counts;
}

/**
 * Accept or reject an issue (E2). The list updates at once; the score comes from the server's
 * reply (it is the only source of truth for the formula). A failed call rolls the list back.
 */
export function useDecision(runId: string) {
  const queryClient = useQueryClient();
  return useMutation<DecisionResponse, Error, { issueId: string } & DecisionRequest, { previous: IssueList | undefined }>({
    mutationFn: ({ issueId, ...body }) => api.decideIssue(issueId, body),
    onMutate: async ({ issueId, decision }) => {
      await queryClient.cancelQueries({ queryKey: keys.issues(runId) });
      const previous = queryClient.getQueryData<IssueList>(keys.issues(runId));
      if (previous) {
        queryClient.setQueryData<IssueList>(keys.issues(runId), {
          ...previous,
          items: previous.items.map((i) => (i.id === issueId ? { ...i, status: decision } : i)),
        });
      }
      return { previous };
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(keys.issues(runId), context.previous);
    },
    onSuccess: (response) => {
      const list = queryClient.getQueryData<IssueList>(keys.issues(runId));
      queryClient.setQueryData<Run | undefined>(keys.run(runId), (run) =>
        run ? { ...run, score: response.score, counts: list ? countIssues(list.items, run.counts) : run.counts } : run,
      );
      void queryClient.invalidateQueries({ queryKey: keys.trace(runId) });
    },
  });
}

export const useDraft = (draftId: string | null) =>
  useQuery({
    queryKey: ["draft", draftId] as const,
    queryFn: () => api.getDraft(draftId!),
    enabled: !!draftId,
    // A reload while the backend is still writing: keep asking until it finishes or fails.
    refetchInterval: (query) => (["queued", "running"].includes(query.state.data?.status ?? "") ? 2000 : false),
  });
