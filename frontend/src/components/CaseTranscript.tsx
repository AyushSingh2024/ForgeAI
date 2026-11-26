"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AgentAnswer } from "@/lib/types";
import CitationList from "./CitationList";

// Drawer showing one eval case end to end: question, expected facts, answer, retrieval, checks, judge.
export default function CaseTranscript({ runId, iteration, caseId, onClose }:
  { runId: string; iteration: string; caseId: string; onClose: () => void }) {
  const q = useQuery({ queryKey: ["case", runId, iteration, caseId], queryFn: () => api.getCase(runId, iteration, caseId) });
  const answer = q.data?.transcript.answer as AgentAnswer | null | undefined;
  const trace = (q.data?.transcript.trace ?? {}) as { hits?: { chunk_id: string; text: string; dense: number }[] };
  const sources = q.data?.case?.sources ?? [];
  const det = q.data?.result.deterministic;
  const checks = det ? (["schema_valid", "citation_exists", "citation_quote_verbatim", "numbers_grounded", "refusal_correct", "tool_correct", "length_ok"] as const) : [];

  return (
    <div className="fixed inset-0 z-50 flex justify-end" style={{ background: "rgba(0,0,0,0.35)" }} onClick={onClose}>
      <aside className="h-full w-full max-w-2xl overflow-y-auto p-6 space-y-4" style={{ background: "var(--surface)" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="font-semibold mono">{caseId}</h3>
          <button className="btn text-sm" onClick={onClose}>Close</button>
        </div>
        {q.isLoading && <p className="muted">Loading…</p>}
        {q.data && (
          <>
            <p className="text-lg">{q.data.case?.question}</p>
            <p className="text-sm muted">expected: {q.data.case?.expected_behavior} · category {q.data.case?.category}</p>
            {q.data.case?.key_facts.length ? <ul className="list-disc pl-5 text-sm">{q.data.case.key_facts.map((f, i) => <li key={i}>{f.fact}</li>)}</ul> : null}
            <div className="card p-4">
              <p className="text-xs muted mb-1">Agent answer {answer?.refused ? "(refused)" : ""}</p>
              <p className="whitespace-pre-wrap">{answer?.answer ?? String(q.data.transcript.error ?? "no answer")}</p>
              {answer?.clarifying_question && <p className="mt-2 italic">{answer.clarifying_question}</p>}
              {answer && <CitationList citations={answer.citations} />}
              {answer?.tool_calls.map((t, i) => <p key={i} className="mono text-xs mt-1">tool {t.tool}({JSON.stringify(t.arguments)}) → {JSON.stringify(t.result)?.slice(0, 200)}</p>)}
            </div>
            <div>
              <p className="text-xs muted mb-1">Retrieved passages (gold = contains the expected source quote)</p>
              {(trace.hits ?? []).map((h, i) => {
                const gold = sources.some((s) => h.text.toLowerCase().includes(s.quote.toLowerCase().slice(0, 60)));
                return <p key={h.chunk_id} className="text-xs mono mb-1" style={{ color: gold ? "var(--success)" : undefined }}>
                  {i + 1}. {h.chunk_id} ({h.dense.toFixed(2)}) {gold ? "★ gold" : ""}</p>;
              })}
            </div>
            {det && (
              <div className="flex flex-wrap gap-2 text-xs">
                {checks.map((k) => <span key={k} className="card px-2 py-1" style={{ color: det[k] ? "var(--success)" : "var(--danger)" }}>{det[k] ? "✓" : "✕"} {k}</span>)}
                <span className="card px-2 py-1">key facts {det.key_fact_coverage === null ? "-" : `${Math.round(det.key_fact_coverage * 100)}%`}</span>
              </div>
            )}
            {!q.data.result.judge.skipped && (
              <div className="card p-4 text-sm">
                <p className="text-xs muted mb-1">Judge ({q.data.result.judge.judge_model})</p>
                <p>faithfulness {q.data.result.judge.faithfulness} · relevance {q.data.result.judge.relevance} · tone {q.data.result.judge.tone}</p>
                <p className="muted mt-1">{q.data.result.judge.rationale}</p>
              </div>
            )}
            {q.data.result.failure_class && <p className="text-sm">Failure class: <b>{q.data.result.failure_class}</b> <span className="muted">{q.data.result.failure_reason}</span></p>}
          </>
        )}
      </aside>
    </div>
  );
}
