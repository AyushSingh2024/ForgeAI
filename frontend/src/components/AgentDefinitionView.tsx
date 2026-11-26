"use client";

import { useState } from "react";
import type { AgentDefinition } from "@/lib/types";

interface Props {
  agent: AgentDefinition;
  yaml: string;
  versions: { version: number; data: AgentDefinition }[];
}

export default function AgentDefinitionView({ agent, yaml, versions }: Props) {
  const [raw, setRaw] = useState(false);
  const [v, setV] = useState(agent.version);
  const shown = versions.find((x) => x.version === v)?.data ?? agent;
  const prev = versions.find((x) => x.version === v - 1)?.data;
  const changed = (slot: string) => prev && prev.system_prompt.slots[slot] !== shown.system_prompt.slots[slot];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-lg font-semibold">{shown.name}</h3>
        {versions.length > 1 && (
          <select className="input w-auto text-sm" value={v} onChange={(e) => setV(Number(e.target.value))}>
            {versions.map((x) => <option key={x.version} value={x.version}>v{x.version}{x.version === agent.version ? " (final)" : ""}</option>)}
          </select>
        )}
        <button className="btn text-sm ml-auto" onClick={() => setRaw(!raw)}>{raw ? "Formatted" : "Raw YAML"}</button>
        {raw && <button className="btn text-sm" onClick={() => navigator.clipboard.writeText(yaml)}>Copy</button>}
      </div>
      {raw ? (
        <pre className="card mono overflow-x-auto p-4 text-xs">{yaml}</pre>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="card p-4">
              <p className="text-xs muted mb-1">Model</p>
              <p className="mono">{shown.model.provider}:{shown.model.name}</p>
              <p className="text-sm muted">temperature {shown.model.temperature}, max tokens {shown.model.max_tokens}</p>
            </div>
            <div className="card p-4">
              <p className="text-xs muted mb-1">Tools ({shown.tools.length})</p>
              {shown.tools.length === 0 ? <p className="muted text-sm">none: documents only</p> :
                shown.tools.map((t) => <p key={t.name} className="text-sm"><span className="mono">{t.name}</span> <span className="muted">{t.reason}</span></p>)}
            </div>
          </div>
          <div className="card p-4">
            <p className="text-xs muted mb-2">Retrieval</p>
            <p className="text-sm mono">
              {shown.retrieval.mode} · chunk {shown.retrieval.chunk_size}/{shown.retrieval.chunk_overlap} · top_k {shown.retrieval.top_k} ·
              bm25 {shown.retrieval.bm25_weight} · rerank {String(shown.retrieval.rerank)} · rewrite {String(shown.retrieval.query_rewrite)} ·
              min_score {shown.retrieval.min_score}
            </p>
            <ul className="mt-2 list-disc pl-5 text-sm muted">{shown.retrieval.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          </div>
          <div className="card p-4 space-y-3">
            <p className="text-xs muted">System prompt slots{prev ? " (highlighted = changed from the previous version)" : ""}</p>
            {Object.entries(shown.system_prompt.slots).filter(([, t]) => t).map(([slot, text]) => (
              <details key={slot} open={!!changed(slot)}>
                <summary className="cursor-pointer font-medium" style={{ color: changed(slot) ? "var(--warning)" : undefined }}>{slot}</summary>
                <p className="text-sm mt-1 whitespace-pre-wrap">{text}</p>
              </details>
            ))}
            {shown.system_prompt.few_shots.length > 0 && <p className="text-sm muted">+ {shown.system_prompt.few_shots.length} few-shot example(s)</p>}
          </div>
          <div className="card p-4 text-sm">
            <p className="text-xs muted mb-1">Output contract & refusal</p>
            <p>max {shown.output_contract.max_words} words, citations {shown.output_contract.require_citations ? "required" : "optional"}</p>
            <p className="muted">“{shown.refusal_message}”</p>
          </div>
        </>
      )}
    </div>
  );
}
