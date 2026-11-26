"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RunDetail } from "@/lib/types";

const POLL_MS = Number(process.env.NEXT_PUBLIC_POLL_MS || 2000);
const ACTIVE = new Set(["queued", "running"]);

export function useRun(runId: string) {
  const q = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api.getRun(runId),
    refetchInterval: (query) => (query.state.data && ACTIVE.has(query.state.data.status) ? POLL_MS : false),
  });
  const run = q.data as RunDetail | undefined;
  return {
    ...q,
    run,
    isActive: !!run && ACTIVE.has(run.status),
    isAwaitingAnswers: run?.status === "awaiting_answers",
    isDone: !!run && ["completed", "budget_stopped"].includes(run.status),
  };
}
