"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

// Nav pill: is the Render backend reachable, and are the LLM providers healthy?
export default function BackendStatus() {
  const q = useQuery({ queryKey: ["health-deep"], queryFn: api.healthDeep, refetchInterval: 30_000, retry: 1 });
  let color = "var(--warning)";
  let label = "waking up…";
  let title = "The free backend may take up to a minute to wake up.";
  if (q.data) {
    const failing = Object.entries(q.data.checks).filter(([, c]) => !c.ok);
    if (failing.length === 0) {
      color = "var(--success)";
      label = "backend ok";
      title = Object.entries(q.data.checks).map(([k, c]) => `${k}: ${c.detail}`).join("\n");
    } else {
      color = "var(--danger)";
      label = `${failing[0][0]} down`;
      title = failing.map(([k, c]) => `${k}: ${c.detail}`).join("\n");
    }
  } else if (q.isError && !q.isFetching) {
    color = "var(--danger)";
    label = "backend unreachable";
    title = (q.error as Error).message;
  }
  return (
    <span title={title} className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs card">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}
