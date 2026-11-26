import { duration, stageLabel } from "@/lib/format";
import type { Stage } from "@/lib/types";

const ICON: Record<string, { sym: string; color: string }> = {
  pending: { sym: "○", color: "var(--muted)" },
  running: { sym: "◐", color: "var(--accent)" },
  done: { sym: "●", color: "var(--success)" },
  failed: { sym: "✕", color: "var(--danger)" },
  skipped: { sym: "–", color: "var(--muted)" },
  waiting: { sym: "?", color: "var(--warning)" },
};

export default function StageTimeline({ stages }: { stages: Stage[] }) {
  return (
    <ol className="space-y-3">
      {stages.map((s) => {
        const icon = ICON[s.status] ?? ICON.pending;
        const ms = s.started_at && s.finished_at ? (s.finished_at - s.started_at) * 1000 : null;
        return (
          <li key={s.name} className="flex gap-3">
            <span className={`mt-0.5 w-4 text-center ${s.status === "running" ? "animate-pulse" : ""}`}
              style={{ color: icon.color }}>{icon.sym}</span>
            <div className="min-w-0">
              <div className="flex items-baseline gap-2">
                <span className="font-medium">{stageLabel[s.name] ?? s.name}</span>
                {ms !== null && <span className="text-xs muted">{duration(ms)}</span>}
              </div>
              {s.message && <p className="text-sm muted break-words">{s.message}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
