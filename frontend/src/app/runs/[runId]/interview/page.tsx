"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import InterviewPanel from "@/components/InterviewPanel";
import { useRun } from "@/hooks/useRun";

export default function InterviewPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const { run, isAwaitingAnswers } = useRun(runId);

  useEffect(() => {
    if (run && !isAwaitingAnswers) router.replace(`/runs/${runId}`);
  }, [run, isAwaitingAnswers, router, runId]);

  return (
    <div className="mx-auto max-w-2xl card p-6 space-y-4">
      <h1 className="text-xl font-bold">A few questions before building</h1>
      <InterviewPanel runId={runId} onDone={() => router.push(`/runs/${runId}`)} />
    </div>
  );
}
