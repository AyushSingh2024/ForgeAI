import type { Citation } from "@/lib/types";

export default function CitationList({ citations }: { citations: Citation[] }) {
  if (!citations.length) return null;
  return (
    <div className="mt-3 space-y-1">
      <p className="text-xs muted">Sources</p>
      {citations.map((c, i) => (
        <details key={i} className="text-sm">
          <summary className="cursor-pointer">
            [{i + 1}] <span className="mono">{c.doc_id}</span>{c.page ? ` p.${c.page}` : ""}
          </summary>
          <p className="mono mt-1 rounded p-2" style={{ background: "var(--bg)" }}>“{c.quote}”</p>
        </details>
      ))}
    </div>
  );
}
