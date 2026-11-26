"use client";

import { Fragment, useMemo, useState } from "react";
import type { EvalCase } from "@/lib/types";

interface Props {
  cases: EvalCase[];
  rejected: EvalCase[];
  stats: Record<string, unknown>;
}

export default function EvalTable({ cases, rejected, stats }: Props) {
  const [tab, setTab] = useState<"accepted" | "rejected">("accepted");
  const [cat, setCat] = useState("all");
  const [split, setSplit] = useState("all");
  const [open, setOpen] = useState<string | null>(null);
  const list = tab === "accepted" ? cases : rejected;
  const cats = useMemo(() => Array.from(new Set(cases.map((c) => c.category))).sort(), [cases]);
  const rows = list.filter((c) => (cat === "all" || c.category === cat) && (split === "all" || c.split === split));
  const counts = cats.map((c) => [c, cases.filter((x) => x.category === c).length] as const);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {counts.map(([c, n]) => <span key={c} className="card px-2 py-1 text-xs">{c}: <b>{n}</b></span>)}
        <span className="card px-2 py-1 text-xs">rejection rate: <b>{Math.round(Number(stats.rejection_rate ?? 0) * 100)}%</b></span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button className={`btn text-sm ${tab === "accepted" ? "btn-primary" : ""}`} onClick={() => setTab("accepted")}>Accepted ({cases.length})</button>
        <button className={`btn text-sm ${tab === "rejected" ? "btn-primary" : ""}`} onClick={() => setTab("rejected")}>Rejected ({rejected.length})</button>
        <select className="input w-auto text-sm" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="all">all categories</option>{cats.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select className="input w-auto text-sm" value={split} onChange={(e) => setSplit(e.target.value)}>
          <option value="all">all splits</option><option>train</option><option>holdout</option>
        </select>
      </div>
      <table className="data">
        <thead><tr><th>id</th><th>category</th><th>split</th><th>question</th><th>expected</th><th>{tab === "accepted" ? "facts" : "rejected because"}</th></tr></thead>
        <tbody>
          {rows.map((c) => (
            <Fragment key={c.id}>
              <tr className="cursor-pointer" onClick={() => setOpen(open === c.id ? null : c.id)}>
                <td className="mono">{c.id}</td><td>{c.category}</td><td>{c.split}</td><td>{c.question}</td>
                <td>{c.expected_behavior}</td>
                <td>{tab === "accepted" ? c.key_facts.length : <span style={{ color: "var(--danger)" }}>{c.generation.rejected_reason}</span>}</td>
              </tr>
              {open === c.id && (
                <tr><td colSpan={6} className="text-sm">
                  {c.key_facts.length > 0 && <ul className="list-disc pl-5">{c.key_facts.map((f, i) => <li key={i}>{f.fact} <span className="muted">({f.kind})</span></li>)}</ul>}
                  {c.sources.map((s, i) => <p key={i} className="mono muted mt-1">“{s.quote}” · {s.doc_id}{s.page ? ` p.${s.page}` : ""}</p>)}
                  {c.gold_answer && <p className="mt-1">Gold (computed by code): <b>{c.gold_answer}</b></p>}
                  {c.notes && <p className="muted mt-1">{c.notes}</p>}
                  <p className="text-xs muted mt-1">prompt {c.generation.prompt_id} v{c.generation.prompt_version}{c.generation.repairs.length ? ` · repairs: ${c.generation.repairs.join("; ")}` : ""}</p>
                </td></tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
