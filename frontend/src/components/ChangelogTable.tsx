"use client";

import { Fragment, useState } from "react";
import { pct } from "@/lib/format";
import type { ChangeEntry } from "@/lib/types";

const short = (v: unknown) => {
  const s = typeof v === "string" ? v : JSON.stringify(v);
  return s && s.length > 70 ? `${s.slice(0, 67)}…` : s;
};

export default function ChangelogTable({ entries, stopReason }: { entries: ChangeEntry[]; stopReason?: string }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="space-y-3">
      {stopReason && <p className="text-sm muted">Optimizer stopped: {stopReason}</p>}
      {entries.length === 0 ? <p className="muted">No changes were made.</p> : (
        <table className="data">
          <thead><tr><th>iter</th><th>failure class</th><th>change</th><th>cases</th><th>before → after</th><th></th></tr></thead>
          <tbody>
            {entries.map((e, i) => {
              const up = e.score_after.overall > e.score_before.overall;
              const down = e.score_after.overall < e.score_before.overall;
              return (
                <Fragment key={i}>
                  <tr className="cursor-pointer" onClick={() => setOpen(open === i ? null : i)}>
                    <td>{e.iteration}</td><td>{e.failure_class}</td>
                    <td className="text-sm">{e.hypothesis}<div className="mono text-xs muted">{e.changes.map((c) => c.path).join(", ")}</div></td>
                    <td className="mono text-xs">{e.target_case_ids.slice(0, 5).join(", ")}{e.target_case_ids.length > 5 ? "…" : ""}</td>
                    <td style={{ color: up ? "var(--success)" : down ? "var(--danger)" : undefined }}>
                      {pct(e.score_before.overall)} → {pct(e.score_after.overall)}</td>
                    <td><span className="text-xs rounded px-1.5 py-0.5" style={{ border: "1px solid", color: e.kept ? "var(--success)" : "var(--muted)" }}>
                      {e.kept ? "kept" : `reverted${e.reverted_reason ? `: ${e.reverted_reason}` : ""}`}</span></td>
                  </tr>
                  {open === i && (
                    <tr><td colSpan={6}>
                      {e.changes.map((c) => (
                        <div key={c.path} className="mb-2 text-sm">
                          <p className="mono">{c.path}</p>
                          {c.text_diff ? <pre className="mono text-xs overflow-x-auto p-2 rounded" style={{ background: "var(--bg)" }}>{c.text_diff}</pre>
                            : <p className="mono text-xs">{short(c.before)} → {short(c.after)}</p>}
                        </div>
                      ))}
                    </td></tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
