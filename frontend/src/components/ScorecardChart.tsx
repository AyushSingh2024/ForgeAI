"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { pct } from "@/lib/format";
import type { Scorecard } from "@/lib/types";
import CaseTranscript from "./CaseTranscript";

export default function ScorecardChart({ runId, scorecards }: { runId: string; scorecards: Scorecard[] }) {
  const [selected, setSelected] = useState<{ iteration: string; caseId: string } | null>(null);
  const train = scorecards.filter((s) => s.iteration !== "final_holdout");
  const holdout = scorecards.find((s) => s.iteration === "final_holdout");
  const first = train[0];
  const best = train[train.length - 1];
  const [view, setView] = useState<string>(best?.iteration ?? "0");
  const current = scorecards.find((s) => s.iteration === view) ?? best;
  if (!first || !best) return <p className="muted">No scores yet.</p>;

  const line = [
    ...train.map((s) => ({ name: s.iteration === "0" ? "baseline" : `iter ${s.iteration}`, train: Math.round(s.summary.pass_rate * 100) })),
    ...(holdout ? [{ name: "holdout", holdout: Math.round(holdout.summary.pass_rate * 100) }] : []),
  ];
  const cats = Array.from(new Set([...Object.keys(first.summary.by_category), ...Object.keys(best.summary.by_category)]));
  const bars = cats.map((c) => ({
    name: c,
    baseline: Math.round((first.summary.by_category[c] ?? 0) * 100),
    best: Math.round((best.summary.by_category[c] ?? 0) * 100),
    ...(holdout ? { holdout: Math.round((holdout.summary.by_category[c] ?? 0) * 100) } : {}),
  }));
  const rel = best.judge_reliability;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        {[["baseline", first.summary.pass_rate], ["best (train)", best.summary.pass_rate], ["holdout", holdout?.summary.pass_rate ?? null],
          ["hallucination", best.summary.hallucination_rate]].map(([label, v]) => (
          <div key={label as string} className="card p-4"><p className="text-xs muted">{label as string}</p><p className="text-2xl font-semibold">{pct(v as number | null)}</p></div>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card p-4 h-72">
          <p className="text-sm font-medium mb-2">Pass rate by iteration (%)</p>
          <ResponsiveContainer width="100%" height="90%">
            <LineChart data={line}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" /><XAxis dataKey="name" fontSize={12} />
              <YAxis domain={[0, 100]} fontSize={12} /><Tooltip /><Legend />
              <Line type="monotone" dataKey="train" stroke="var(--accent)" strokeWidth={2} dot />
              <Line type="monotone" dataKey="holdout" stroke="var(--success)" strokeWidth={2} dot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="card p-4 h-72">
          <p className="text-sm font-medium mb-2">Pass rate by category (%)</p>
          <ResponsiveContainer width="100%" height="90%">
            <BarChart data={bars}><CartesianGrid strokeDasharray="3 3" stroke="var(--border)" /><XAxis dataKey="name" fontSize={11} />
              <YAxis domain={[0, 100]} fontSize={12} /><Tooltip /><Legend />
              <Bar dataKey="baseline" fill="var(--muted)" /><Bar dataKey="best" fill="var(--accent)" />
              {holdout && <Bar dataKey="holdout" fill="var(--success)" />}
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 text-xs">
        <span className="card px-2 py-1">judge calibration: <b>{rel.calibration_pass === null ? "not measured" : rel.calibration_pass ? `trusted (${rel.calibration_passed}/${rel.calibration_total})` : "NOT trusted"}</b></span>
        <span className="card px-2 py-1">position-swap agreement: <b>{pct(rel.flip_agreement)}</b></span>
        <span className="card px-2 py-1">judge vs checks disagreement: <b>{pct(rel.judge_det_disagreement)}</b></span>
      </div>
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <p className="font-medium">Cases</p>
          <select className="input w-auto text-sm" value={current.iteration} onChange={(e) => setView(e.target.value)}>
            {scorecards.map((s) => <option key={s.iteration} value={s.iteration}>{s.iteration === "final_holdout" ? "holdout" : s.iteration === "0" ? "baseline" : `iteration ${s.iteration}`}</option>)}
          </select>
        </div>
        <table className="data">
          <thead><tr><th>case</th><th>category</th><th>verdict</th><th>failure class</th><th>key facts</th><th>judge</th></tr></thead>
          <tbody>
            {current.cases.map((c) => {
              const scores = [c.judge.faithfulness, c.judge.relevance, c.judge.tone].filter((x): x is number => x !== null);
              return (
                <tr key={c.case_id} className="cursor-pointer" onClick={() => setSelected({ iteration: current.iteration, caseId: c.case_id })}>
                  <td className="mono">{c.case_id}</td><td>{c.category}</td>
                  <td style={{ color: c.verdict === "pass" ? "var(--success)" : "var(--danger)" }}>{c.verdict}</td>
                  <td>{c.failure_class ?? ""}</td><td>{pct(c.deterministic.key_fact_coverage)}</td>
                  <td>{scores.length ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1) : "-"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {selected && <CaseTranscript runId={runId} iteration={selected.iteration} caseId={selected.caseId} onClose={() => setSelected(null)} />}
    </div>
  );
}
