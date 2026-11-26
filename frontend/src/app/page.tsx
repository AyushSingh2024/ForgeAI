"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { pct, relativeTime, stageLabel } from "@/lib/format";
import { STAGES } from "@/lib/types";

export default function Home() {
  const router = useRouter();
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.listRuns });
  const demos = useQuery({ queryKey: ["demos"], queryFn: api.listDemos });
  const demo = useMutation({ mutationFn: (name: string) => api.startDemo(name), onSuccess: (r) => router.push(`/runs/${r.run_id}`) });

  return (
    <div className="space-y-10">
      <section className="space-y-3 pt-6">
        <h1 className="text-3xl font-bold">Turn a brief and a folder of documents into a tested agent.</h1>
        <p className="muted max-w-3xl">
          ForgeAI interviews you (at most 5 questions), checks the documents can support the brief, generates a declarative
          agent, writes 20+ test cases, grades them with code checks and an anti-bias LLM judge, improves the agent with targeted
          fixes, and writes an honest report.
        </p>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <Link href="/builds/new" className="card p-5 hover:opacity-90">
          <p className="font-semibold">Start a new build →</p>
          <p className="text-sm muted mt-1">Upload your brief and documents.</p>
        </Link>
        <div className="card p-5">
          <p className="font-semibold">Try a demo</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {(demos.data ?? []).map((d) => (
              <button key={d.name} className="btn text-sm" disabled={demo.isPending} onClick={() => demo.mutate(d.name)}>
                {d.name.replace("_", " ")}
              </button>
            ))}
            {demos.data?.length === 0 && <p className="text-sm muted">No demos on this server.</p>}
          </div>
          {demo.isError && <p className="text-xs mt-2" style={{ color: "var(--danger)" }}>{(demo.error as Error).message}</p>}
        </div>
        <Link href="/agents" className="card p-5 hover:opacity-90">
          <p className="font-semibold">Chat with a finished agent →</p>
          <p className="text-sm muted mt-1">Every answer cites its sources.</p>
        </Link>
      </section>

      <section>
        <p className="text-xs muted mb-2">Pipeline</p>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {STAGES.map((s, i) => (
            <span key={s} className="flex items-center gap-2">
              <span className="card px-3 py-1">{stageLabel[s]}</span>
              {i < STAGES.length - 1 && <span className="muted">→</span>}
            </span>
          ))}
        </div>
      </section>

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Recent runs</h2>
          <Link href="/runs" className="text-sm" style={{ color: "var(--accent)" }}>all runs</Link>
        </div>
        {runs.isError && <p className="text-sm" style={{ color: "var(--danger)" }}>{(runs.error as Error).message}</p>}
        <div className="card divide-y" style={{ borderColor: "var(--border)" }}>
          {(runs.data ?? []).slice(0, 5).map((r) => (
            <Link key={r.run_id} href={`/runs/${r.run_id}`} className="flex items-center gap-3 px-4 py-3">
              <StatusBadge status={r.status} />
              <span className="flex-1 truncate text-sm">{r.agent_name ?? r.brief_preview}</span>
              <span className="text-sm">{pct(r.holdout_pass_rate ?? r.final_pass_rate)}</span>
              <span className="text-xs muted w-24 text-right">{relativeTime(r.created_at)}</span>
            </Link>
          ))}
          {runs.data?.length === 0 && <p className="px-4 py-3 text-sm muted">No runs yet.</p>}
        </div>
      </section>
    </div>
  );
}
