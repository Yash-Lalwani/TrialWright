// TanStack Query hooks over lib/api.ts. Keys are shared so mutations can update caches.

"use client";

import { useQuery } from "@tanstack/react-query";

import * as api from "./api";

export const keys = {
  health: ["health"] as const,
  protocols: ["protocols"] as const,
  run: (runId: string) => ["run", runId] as const,
  issues: (runId: string) => ["issues", runId] as const,
  completeness: (runId: string) => ["completeness", runId] as const,
  burden: (runId: string) => ["burden", runId] as const,
  peers: (runId: string) => ["peers", runId] as const,
  precedent: (runId: string) => ["precedent", runId] as const,
  trace: (runId: string) => ["trace", runId] as const,
  protocolRuns: (protocolId: string) => ["protocol-runs", protocolId] as const,
  diff: (from: string, to: string) => ["diff", from, to] as const,
  benchmark: ["benchmark"] as const,
  draft: (draftId: string) => ["draft", draftId] as const,
};

export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.getHealth, retry: false });

export const useProtocols = () => useQuery({ queryKey: keys.protocols, queryFn: api.listProtocols });

export const useRun = (runId: string) => useQuery({ queryKey: keys.run(runId), queryFn: () => api.getRun(runId) });

/** All issues for a run; the workspace filters client-side so counts stay visible per filter. */
export const useIssues = (runId: string, enabled = true) =>
  useQuery({ queryKey: keys.issues(runId), queryFn: () => api.listIssues(runId), enabled });

export const useCompleteness = (runId: string, enabled = true) =>
  useQuery({ queryKey: keys.completeness(runId), queryFn: () => api.getCompleteness(runId), enabled });

export const useBurden = (runId: string) => useQuery({ queryKey: keys.burden(runId), queryFn: () => api.getBurden(runId) });

export const usePeers = (runId: string) => useQuery({ queryKey: keys.peers(runId), queryFn: () => api.getPeers(runId) });

export const usePrecedent = (runId: string) =>
  useQuery({ queryKey: keys.precedent(runId), queryFn: () => api.getPrecedent(runId) });

export const useTrace = (runId: string) => useQuery({ queryKey: keys.trace(runId), queryFn: () => api.getTrace(runId) });

export const useProtocolRuns = (protocolId: string | null) =>
  useQuery({
    queryKey: keys.protocolRuns(protocolId ?? ""),
    queryFn: () => api.listProtocolRuns(protocolId!),
    enabled: !!protocolId,
  });

export const useDiff = (from: string | null, to: string | null) =>
  useQuery({ queryKey: keys.diff(from ?? "", to ?? ""), queryFn: () => api.getDiff(from!, to!), enabled: !!from && !!to });

export const useBenchmark = () => useQuery({ queryKey: keys.benchmark, queryFn: api.getBenchmark });

export const useDraft = (draftId: string | null) =>
  useQuery({ queryKey: keys.draft(draftId ?? ""), queryFn: () => api.getDraft(draftId!), enabled: !!draftId });
