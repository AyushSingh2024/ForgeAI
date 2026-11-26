"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { pct } from "@/lib/format";

export default function Agents() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["agents"], queryFn: api.listAgents });
  const [yaml, setYaml] = useState<File | null>(null);
  const [docs, setDocs] = useState<File[]>([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function upload() {
    if (!yaml || !docs.length) return;
    setBusy(true);
    setMsg("");
    const form = new FormData();
    form.append("agent_yaml", yaml);
    docs.forEach((d) => form.append("docs", d));
    try {
      const r = await api.uploadAgent(form);
      setMsg(`Uploaded ${r.name}.`);
      await qc.invalidateQueries({ queryKey: ["agents"] });
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Agents</h1>
      {q.isError && <p style={{ color: "var(--danger)" }}>{(q.error as Error).message}</p>}
      <div className="grid gap-4 md:grid-cols-2">
        {(q.data ?? []).map((a) => (
          <div key={a.agent_id} className="card p-5 space-y-2">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold">{a.name}</h2>
              <span className="text-xs muted">v{a.version}</span>
              {a.source?.includes("demo") && <span className="text-xs muted">demo</span>}
            </div>
            <p className="text-sm muted line-clamp-3">{a.description}</p>
            <div className="flex flex-wrap gap-1">
              {a.tools.length ? a.tools.map((t) => <span key={t} className="mono rounded px-1.5 py-0.5 text-xs" style={{ background: "var(--bg)" }}>{t}</span>)
                : <span className="text-xs muted">documents only</span>}
            </div>
            <p className="text-xs muted">holdout pass rate {pct(a.holdout_pass_rate)} · train {pct(a.pass_rate)}</p>
            <div className="flex gap-2">
              <Link className="btn btn-primary text-sm" href={`/agents/${a.agent_id}/chat`}>Chat</Link>
              <Link className="btn text-sm" href={`/runs/${a.source_run}`}>Run details</Link>
            </div>
          </div>
        ))}
        {q.data?.length === 0 && <p className="muted">No finished agents yet.</p>}
      </div>

      <section className="card p-5 space-y-3">
        <h2 className="font-semibold">Upload any agent.yaml</h2>
        <p className="text-sm muted">The chat runner is generic: it can load any definition that follows the schema, plus its documents.</p>
        <label className="block text-sm">agent.yaml <input type="file" accept=".yaml,.yml" onChange={(e) => setYaml(e.target.files?.[0] ?? null)} /></label>
        <label className="block text-sm">documents <input type="file" multiple onChange={(e) => setDocs(Array.from(e.target.files ?? []))} /></label>
        <button className="btn text-sm" disabled={busy || !yaml || !docs.length} onClick={upload}>Upload</button>
        {msg && <p className="text-sm">{msg}</p>}
      </section>
    </div>
  );
}
