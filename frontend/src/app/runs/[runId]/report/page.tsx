"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "@/lib/api";

// Print-friendly report: the browser's "Save as PDF" gives a clean document for submission.
export default function PrintableReport() {
  const { runId } = useParams<{ runId: string }>();
  const q = useQuery({ queryKey: ["report", runId], queryFn: () => api.getReport(runId) });
  if (q.isLoading) return <p className="muted">Loading report…</p>;
  if (q.isError) return <p style={{ color: "var(--danger)" }}>{(q.error as Error).message}</p>;
  return (
    <div className="mx-auto max-w-4xl">
      <button className="btn text-sm no-print mb-4" onClick={() => window.print()}>Print / save as PDF</button>
      <article className="prose-report">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{q.data ?? ""}</ReactMarkdown>
      </article>
    </div>
  );
}
