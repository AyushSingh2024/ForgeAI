"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

// The intake interview (Req 1): at most 5 questions. Empty answers keep the suggested default.
export default function InterviewPanel({ runId, onDone }: { runId: string; onDone?: () => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["interview", runId], queryFn: () => api.getInterview(runId) });
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (q.data) setAnswers(Object.fromEntries(q.data.questions.map((x) => [x.id, x.default || ""])));
  }, [q.data]);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await qc.invalidateQueries({ queryKey: ["run", runId] });
      onDone?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (q.isLoading) return <p className="muted">Loading questions…</p>;
  const questions = q.data?.questions ?? [];
  if (!questions.length) return <p className="muted">No questions for this run.</p>;

  return (
    <div className="space-y-5">
      <p className="text-sm muted">I have {questions.length} question(s) before building the agent. Leave an answer empty to keep my guess.</p>
      {questions.map((x, i) => (
        <div key={x.id} className="space-y-2">
          <p className="font-medium"><span className="muted mr-2">{i + 1}/{questions.length}</span>{x.text}</p>
          {x.why && <p className="text-xs muted">Why: {x.why}</p>}
          {x.kind === "free_text" ? (
            <input className="input" value={answers[x.id] ?? ""} placeholder="(keep the current plan)"
              onChange={(e) => setAnswers({ ...answers, [x.id]: e.target.value })} />
          ) : (
            <div className="flex flex-wrap gap-2">
              {(x.kind === "yes_no" ? ["yes", "no"] : x.options).map((o) => (
                <button key={o} type="button" className={`btn text-sm ${answers[x.id] === o ? "btn-primary" : ""}`}
                  onClick={() => setAnswers({ ...answers, [x.id]: o })}>{o}</button>
              ))}
            </div>
          )}
        </div>
      ))}
      {error && <p className="text-sm" style={{ color: "var(--danger)" }}>{error}</p>}
      <div className="flex gap-2">
        <button className="btn btn-primary" disabled={busy} onClick={() => act(() => api.submitAnswers(runId, answers))}>
          Submit answers
        </button>
        <button className="btn" disabled={busy} onClick={() => act(() => api.skipInterview(runId))}>
          Skip, let it assume
        </button>
      </div>
    </div>
  );
}
