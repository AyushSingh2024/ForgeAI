"use client";

import { useEffect, useRef, useState } from "react";
import { useChat } from "@/hooks/useChat";
import type { ChatResponse } from "@/lib/types";
import CitationList from "./CitationList";

interface Props {
  agentId: string;
  suggestions?: string[];
  onAnswer?: (r: ChatResponse) => void;
}

export default function ChatWindow({ agentId, suggestions = [], onAnswer }: Props) {
  const { messages, loading, send, retry, clear } = useChat(agentId);
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
    const last = messages[messages.length - 1];
    if (last?.response) onAnswer?.(last.response);
  }, [messages, onAnswer]);

  function submit() {
    if (!text.trim()) return;
    void send(text);
    setText("");
  }

  return (
    <div className="card flex h-[70vh] flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="muted text-sm">Ask a question. Answers come only from the agent&apos;s documents and tools, with sources.</p>
            {suggestions.slice(0, 4).map((s) => (
              <button key={s} className="btn text-sm block text-left" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            {m.role === "user" ? (
              <p className="max-w-[80%] rounded-xl px-3 py-2 text-white" style={{ background: "var(--accent)" }}>{m.content}</p>
            ) : m.error ? (
              <div className="text-sm" style={{ color: "var(--danger)" }}>{m.error} <button className="underline" onClick={retry}>retry</button></div>
            ) : (
              <div className="max-w-[90%] rounded-xl border px-3 py-2"
                style={{ borderColor: m.response?.refused ? "var(--warning)" : "var(--border)" }}>
                <p className="whitespace-pre-wrap">{m.content}</p>
                {m.response?.clarifying_question && m.response.clarifying_question !== m.content && (
                  <p className="mt-2 italic">{m.response.clarifying_question}</p>
                )}
                {m.response?.refused && m.response.refusal_reason && <p className="mt-1 text-xs muted">refused: {m.response.refusal_reason}</p>}
                {m.response?.tool_calls.map((t, j) => (
                  <span key={j} className="mono mr-2 mt-2 inline-block rounded px-1.5 py-0.5 text-xs" style={{ background: "var(--bg)" }}>
                    {t.tool}: {JSON.stringify(t.arguments).slice(0, 60)}
                  </span>
                ))}
                {m.response && <CitationList citations={m.response.citations} />}
              </div>
            )}
          </div>
        ))}
        {loading && <p className="muted text-sm animate-pulse">thinking…</p>}
        <div ref={bottom} />
      </div>
      <div className="flex gap-2 border-t p-3" style={{ borderColor: "var(--border)" }}>
        <input className="input" value={text} disabled={loading} placeholder="Type a question and press Enter"
          onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submit()} />
        <button className="btn btn-primary" disabled={loading || !text.trim()} onClick={submit}>Send</button>
        <button className="btn" onClick={clear} title="Clear conversation">Clear</button>
      </div>
    </div>
  );
}
