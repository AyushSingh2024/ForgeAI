"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { pct, relativeTime, truncate } from "@/lib/format";

export default function Runs() {
  const q = useQuery({ queryKey: ["runs"], queryFn: api.listRuns, refetchInterval: 10_000 });
  const [status, setStatus] = useState("all");
  const runs = (q.data ?? []).filter((r) => status === "all" || r.status === status);
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">Runs</h1>
        <select className="input w-auto text-sm ml-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
          {["all", "queued", "running", "awaiting_answers", "completed", "budget_stopped", "failed", "cancelled"].map((s) => <option key={s}>{s}</option>)}
        </select>
      </div>
      {q.isError && <p style={{ color: "var(--danger)" }}>{(q.error as Error).message}</p>}
      <table className="data card">
        <thead><tr><th>created</th><th>brief / agent</th><th>status</th><th>train</th><th>holdout</th></tr></thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.run_id}>
              <td className="text-xs muted">{relativeTime(r.created_at)}</td>
              <td>
                <Link href={`/runs/${r.run_id}`} style={{ color: "var(--accent)" }}>{r.agent_name ?? truncate(r.brief_preview, 90)}</Link>
                {r.source?.includes("demo") && <span className="ml-2 text-xs muted">demo</span>}
              </td>
              <td><StatusBadge status={r.status} /></td>
              <td>{pct(r.final_pass_rate)}</td>
              <td>{pct(r.holdout_pass_rate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {q.data && runs.length === 0 && <p className="muted">No runs yet. <Link href="/builds/new" style={{ color: "var(--accent)" }}>Start a build</Link> or try a demo.</p>}
    </div>
  );
}
