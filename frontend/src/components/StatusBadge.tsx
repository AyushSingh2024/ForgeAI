import type { RunStatus } from "@/lib/types";

const MAP: Record<string, { label: string; color: string }> = {
  queued: { label: "queued", color: "var(--muted)" },
  running: { label: "running", color: "var(--accent)" },
  awaiting_answers: { label: "needs answers", color: "var(--warning)" },
  completed: { label: "completed", color: "var(--success)" },
  budget_stopped: { label: "stopped (budget)", color: "var(--warning)" },
  failed: { label: "failed", color: "var(--danger)" },
  cancelled: { label: "cancelled", color: "var(--muted)" },
  uploaded: { label: "uploaded", color: "var(--accent)" },
  unknown: { label: "unknown", color: "var(--muted)" },
};

export default function StatusBadge({ status }: { status: RunStatus | string }) {
  const s = MAP[status] ?? MAP.unknown;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs"
      style={{ borderColor: s.color, color: s.color }}>
      <span className={`h-1.5 w-1.5 rounded-full ${status === "running" ? "animate-pulse" : ""}`}
        style={{ background: s.color }} />
      {s.label}
    </span>
  );
}
