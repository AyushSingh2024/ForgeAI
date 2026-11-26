import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function ReportView({ markdown, runId }: { markdown: string; runId?: string }) {
  const headings = markdown.split("\n").filter((l) => l.startsWith("## ")).map((l) => l.slice(3));
  return (
    <div className="grid gap-6 md:grid-cols-[200px_1fr]">
      <aside className="no-print hidden md:block text-sm space-y-1">
        <p className="text-xs muted mb-2">Contents</p>
        {headings.map((h) => <p key={h} className="muted">{h}</p>)}
        {runId && <Link href={`/runs/${runId}/report`} className="block mt-4" style={{ color: "var(--accent)" }}>Printable version</Link>}
      </aside>
      <article className="prose-report card p-6 overflow-x-auto">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
      </article>
    </div>
  );
}
