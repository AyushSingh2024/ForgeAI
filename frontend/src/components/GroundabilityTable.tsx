"use client";

import { Fragment, useState } from "react";
import { pct } from "@/lib/format";
import type { GroundabilityReport } from "@/lib/types";

const COLOR: Record<string, string> = {
  supported: "var(--success)", partial: "var(--warning)", unsupported: "var(--danger)", needs_tool: "var(--accent)",
};

export default function GroundabilityTable({ report }: { report: GroundabilityReport }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="space-y-4">
      <p>Coverage: <b>{pct(report.coverage)}</b> of {report.verdicts.length} asks are supported by the documents or a tool.</p>
      {report.warnings.length > 0 && (
        <div className="card p-4 text-sm space-y-1" style={{ borderColor: "var(--warning)" }}>
          {report.warnings.map((w) => <p key={w}>⚠ {w}</p>)}
        </div>
      )}
      <table className="data">
        <thead><tr><th>ask</th><th>verdict</th><th>evidence</th></tr></thead>
        <tbody>
          {report.verdicts.map((v) => (
            <Fragment key={v.ask_id}>
              <tr className="cursor-pointer" onClick={() => setOpen(open === v.ask_id ? null : v.ask_id)}>
                <td>{v.ask_text}<div className="text-xs muted">{v.source}</div></td>
                <td><span style={{ color: COLOR[v.verdict] }}>{v.verdict.replace("_", " ")}{v.needed_tool ? `: ${v.needed_tool}` : ""}</span></td>
                <td className="muted text-sm">{v.explanation}</td>
              </tr>
              {open === v.ask_id && (
                <tr><td colSpan={3}>
                  {v.probes.map((p, i) => (
                    <div key={i} className="mb-2 text-sm">
                      <p>Probe: {p.question}</p>
                      {p.supporting_quote ? (
                        <p className="mono" style={{ color: "var(--success)" }}>“{p.supporting_quote}” <span className="muted">({p.supporting_chunk_id})</span></p>
                      ) : (
                        <p className="muted">no verified quote{p.llm_said_supported ? " (the model claimed support, but the quote was not in the passages)" : ""}</p>
                      )}
                    </div>
                  ))}
                </td></tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
