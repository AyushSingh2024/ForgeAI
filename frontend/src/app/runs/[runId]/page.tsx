"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import AgentDefinitionView from "@/components/AgentDefinitionView";
import ChangelogTable from "@/components/ChangelogTable";
import EvalTable from "@/components/EvalTable";
import GroundabilityTable from "@/components/GroundabilityTable";
import InterviewPanel from "@/components/InterviewPanel";
import ReportView from "@/components/ReportView";
import RequirementsView from "@/components/RequirementsView";
import ScorecardChart from "@/components/ScorecardChart";
import StageTimeline from "@/components/StageTimeline";
import StatusBadge from "@/components/StatusBadge";
import { useRun } from "@/hooks/useRun";
import { api } from "@/lib/api";

const TABS = [
  ["report", "Report"], ["requirements", "Requirements"], ["groundability", "Groundability"], ["agent", "Agent"],
  ["evals", "Evals"], ["scorecards", "Scores"], ["changelog", "Changes"],
] as const;
type Tab = (typeof TABS)[number][0];

function TabBody({ tab, runId, isActive }: { tab: Tab; runId: string; isActive: boolean }) {
  const refetch = isActive ? 8000 : false;
  const q = useQuery({
    queryKey: [tab, runId],
    refetchInterval: refetch,
    queryFn: async (): Promise<unknown> => {
      switch (tab) {
        case "requirements": return api.getRequirements(runId);
        case "groundability": return api.getGroundability(runId);
        case "agent": return api.getAgent(runId);
        case "evals": return api.getEvals(runId);
        case "scorecards": return api.getScorecards(runId);
        case "changelog": return api.getChangelog(runId);
        case "report": return api.getReport(runId);
      }
    },
  });
  if (q.isLoading) return <p className="muted">Loading…</p>;
  if (q.isError) return <p className="muted">{(q.error as Error).message}</p>;
  const d = q.data as never;
  switch (tab) {
    case "requirements": return <RequirementsView req={(d as { data: never }).data} />;
    case "groundability": return <GroundabilityTable report={d} />;
    case "agent": {
      const a = d as { data: never; yaml: string; versions: never[] };
      return <AgentDefinitionView agent={a.data} yaml={a.yaml} versions={a.versions} />;
    }
    case "evals": {
      const e = d as { cases: never[]; rejected: never[]; stats: Record<string, unknown> };
      return <EvalTable cases={e.cases} rejected={e.rejected} stats={e.stats} />;
    }
    case "scorecards": return <ScorecardChart runId={runId} scorecards={(d as { scorecards: never[] }).scorecards} />;
    case "changelog": {
      const c = d as { entries: never[]; summary: { stop_reason: string } | null };
      return <ChangelogTable entries={c.entries} stopReason={c.summary?.stop_reason} />;
    }
    case "report": return <ReportView markdown={d as string} runId={runId} />;
  }
}

export default function RunPage() {
  const { runId } = useParams<{ runId: string }>();
  const qc = useQueryClient();
  const { run, isLoading, isError, error, isActive, isAwaitingAnswers, isDone } = useRun(runId);
  const [tab, setTab] = useState<Tab | null>(null);
  const [busy, setBusy] = useState(false);

  if (isLoading) return <p className="muted">Loading run… (the backend may be waking up)</p>;
  if (isError || !run) return <p style={{ color: "var(--danger)" }}>{(error as Error)?.message ?? "Run not found"}</p>;

  const availableKey: Record<Tab, keyof typeof run.available> = {
    report: "report", requirements: "requirements", groundability: "groundability", agent: "agent", evals: "evals",
    scorecards: "scorecards", changelog: "changelog",
  };
  const tabs = TABS.filter(([k]) => run.available[availableKey[k]]);
  const activeTab = tab && tabs.some(([k]) => k === tab) ? tab : tabs[0]?.[0] ?? null;

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    try {
      await fn();
      await qc.invalidateQueries({ queryKey: ["run", runId] });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-bold mono">{run.run_id}</h1>
          <StatusBadge status={run.status} />
          {run.queue_position && <span className="text-xs muted">position {run.queue_position} in queue</span>}
          <div className="ml-auto flex gap-2">
            {isActive && <button className="btn text-sm" disabled={busy} onClick={() => act(() => api.cancelRun(runId))}>Cancel</button>}
            {["failed", "cancelled", "budget_stopped"].includes(run.status) && (
              <button className="btn text-sm" disabled={busy} onClick={() => act(() => api.resumeRun(runId))}>Resume from last stage</button>
            )}
            <a className="btn text-sm" href={api.downloadUrl(runId)}>Download zip</a>
            {run.available.agent && isDone && <Link className="btn btn-primary text-sm" href={`/agents/${runId}/chat`}>Chat with this agent</Link>}
          </div>
        </div>
        <p className="text-sm muted max-w-4xl">{run.brief}</p>
        {run.error && <p className="text-sm" style={{ color: "var(--danger)" }}>Error: {run.error}</p>}
      </header>

      {isAwaitingAnswers && (
        <section className="card p-5" style={{ borderColor: "var(--warning)" }}>
          <h2 className="font-semibold mb-3">The factory needs your answers</h2>
          <InterviewPanel runId={runId} />
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <aside className="card p-4 h-fit"><StageTimeline stages={run.stages} /></aside>
        <section className="min-w-0 space-y-4">
          {tabs.length === 0 ? <p className="muted">Artifacts will appear here as the stages finish.</p> : (
            <>
              <div className="flex flex-wrap gap-1 border-b pb-2" style={{ borderColor: "var(--border)" }}>
                {tabs.map(([k, label]) => (
                  <button key={k} className={`btn text-sm ${activeTab === k ? "btn-primary" : ""}`} onClick={() => setTab(k)}>{label}</button>
                ))}
              </div>
              {activeTab && <TabBody key={activeTab} tab={activeTab} runId={runId} isActive={isActive} />}
            </>
          )}
          {run.notes.length > 0 && (
            <div className="card p-4 text-sm"><p className="text-xs muted mb-1">Notes</p>{run.notes.map((n) => <p key={n}>• {n}</p>)}</div>
          )}
        </section>
      </div>
    </div>
  );
}
