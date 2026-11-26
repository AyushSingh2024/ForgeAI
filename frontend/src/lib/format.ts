// Small display helpers.

export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "-" : `${Math.round(v * 100)}%`);

export function duration(ms: number | null | undefined): string {
  if (!ms || ms < 0) return "-";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

export function relativeTime(epochSeconds: number | null | undefined): string {
  if (!epochSeconds) return "-";
  const diff = Date.now() / 1000 - epochSeconds;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return new Date(epochSeconds * 1000).toLocaleDateString();
}

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export const truncate = (text: string, n: number) => (text.length > n ? `${text.slice(0, n - 1)}…` : text);

export const stageLabel: Record<string, string> = {
  ingest: "Read documents",
  intake: "Interview",
  guard: "Groundability check",
  generate_agent: "Generate agent",
  generate_evals: "Generate tests",
  evaluate_0: "Baseline evaluation",
  optimize: "Optimize",
  final_holdout: "Holdout test",
  report: "Report",
};
