"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import ChatWindow from "@/components/ChatWindow";
import { api } from "@/lib/api";
import type { ChatResponse } from "@/lib/types";

export default function ChatPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const q = useQuery({ queryKey: ["agent-def", agentId], queryFn: () => api.getAgentDef(agentId) });
  const [last, setLast] = useState<ChatResponse | null>(null);
  const [showWhy, setShowWhy] = useState(true);
  const a = q.data?.data;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">{a?.name ?? "Agent"}</h1>
        {a && <span className="text-xs muted">v{a.version}</span>}
        {a?.tools.map((t) => <span key={t.name} className="mono rounded px-1.5 py-0.5 text-xs" style={{ background: "var(--surface)" }}>{t.name}</span>)}
        <button className="btn text-sm ml-auto" onClick={() => setShowWhy(!showWhy)}>{showWhy ? "Hide" : "Show"} “why this answer”</button>
      </header>
      {q.isError && <p style={{ color: "var(--danger)" }}>{(q.error as Error).message}</p>}
      <div className={`grid gap-4 ${showWhy ? "lg:grid-cols-[1fr_340px]" : ""}`}>
        <ChatWindow agentId={agentId} suggestions={a?.suggested_questions ?? []} onAnswer={setLast} />
        {showWhy && (
          <aside className="card p-4 h-[70vh] overflow-y-auto text-sm space-y-3">
            <p className="text-xs muted">Why this answer (last reply)</p>
            {!last ? <p className="muted">Ask something to see the retrieved passages and tool calls.</p> : (
              <>
                <p>best retrieval score: <b>{last.trace.best_score?.toFixed(3) ?? "-"}</b>
                  {last.trace.deterministic_refusal ? " · refused before calling the model (nothing relevant found)" : ""}</p>
                {last.tool_calls.map((t, i) => (
                  <div key={i} className="mono text-xs rounded p-2" style={{ background: "var(--bg)" }}>
                    {t.tool}({JSON.stringify(t.arguments)})<br />→ {t.error ?? JSON.stringify(t.result)?.slice(0, 300)}
                  </div>
                ))}
                {last.trace.hits.map((h, i) => (
                  <div key={h.chunk_id}>
                    <p className="mono text-xs">{i + 1}. {h.doc_id} p.{h.page} · dense {h.dense.toFixed(2)} · bm25 {h.bm25.toFixed(1)}</p>
                    <p className="text-xs muted">{h.text}</p>
                  </div>
                ))}
                {last.trace.invalid_citations.length > 0 && (
                  <p className="text-xs" style={{ color: "var(--warning)" }}>{last.trace.invalid_citations.length} citation(s) were dropped because the quote was not in the passage.</p>
                )}
              </>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}
