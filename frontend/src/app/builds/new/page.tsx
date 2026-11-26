"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import BriefForm from "@/components/BriefForm";
import DocUploader from "@/components/DocUploader";
import { api } from "@/lib/api";

export default function NewBuild() {
  const router = useRouter();
  const [brief, setBrief] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<"interactive" | "unattended">("interactive");
  const [answers, setAnswers] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const valid = brief.trim().length >= 20 && brief.trim().length <= 3000 && files.length > 0;

  async function submit() {
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("brief", brief.trim());
    form.append("mode", mode);
    files.forEach((f) => form.append("files", f));
    if (answers) form.append("answers_yaml", answers);
    try {
      const r = await api.createBuild(form);
      router.push(`/runs/${r.run_id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">New build</h1>
      <div className="card p-5 space-y-6">
        <BriefForm value={brief} onChange={setBrief} />
        <DocUploader files={files} onChange={setFiles} />
        <div className="space-y-2">
          <span className="font-medium">Mode</span>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={`btn text-sm ${mode === "interactive" ? "btn-primary" : ""}`} onClick={() => setMode("interactive")}>
              Interactive: answer up to 5 questions
            </button>
            <button type="button" className={`btn text-sm ${mode === "unattended" ? "btn-primary" : ""}`} onClick={() => setMode("unattended")}>
              Unattended: assume the answers
            </button>
          </div>
        </div>
        <details>
          <summary className="cursor-pointer text-sm muted">Advanced: scripted interview answers (answers.yaml)</summary>
          <input type="file" accept=".yaml,.yml" className="mt-2 text-sm" onChange={(e) => setAnswers(e.target.files?.[0] ?? null)} />
        </details>
        {error && <p className="text-sm" style={{ color: "var(--danger)" }}>{error}</p>}
        <button className="btn btn-primary" disabled={!valid || busy} onClick={submit}>
          {busy ? "Uploading…" : "Forge the agent"}
        </button>
      </div>
    </div>
  );
}
