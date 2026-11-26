// The ONLY place that calls the backend. Every function mirrors a route in backend/app/api/*.
import type {
  AgentDefinition, AgentSummary, ChangeEntry, ChatResponse, EvalCase, GroundabilityReport, Health, Question,
  Requirements, RunDetail, RunSummary, Scorecard,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs = 60_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs); // Render free cold starts can take ~1 min
  const headers = new Headers(init.headers);
  if (API_KEY) headers.set("X-API-Key", API_KEY);
  try {
    const res = await fetch(`${API_URL}${path}`, { ...init, headers, signal: controller.signal });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
      } catch {
        /* not json */
      }
      throw new ApiError(res.status, detail);
    }
    const type = res.headers.get("content-type") || "";
    return (type.includes("application/json") ? await res.json() : await res.text()) as T;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if ((e as Error).name === "AbortError") throw new ApiError(0, "The backend did not answer in time (it may be waking up).");
    throw new ApiError(0, "Cannot reach the backend. Check NEXT_PUBLIC_API_URL and that the server is running.");
  } finally {
    clearTimeout(timer);
  }
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<{ status: string; version: string }>("/health", {}, 90_000),
  healthDeep: () => request<Health>("/api/health/deep", {}, 90_000),

  createBuild: (form: FormData) => request<{ run_id: string }>("/api/builds", { method: "POST", body: form }, 120_000),
  listDemos: () => request<{ name: string; brief: string; has_committed_run: boolean }[]>("/api/builds/demos"),
  startDemo: (name: string, mode = "unattended") =>
    request<{ run_id: string }>(`/api/builds/demo/${encodeURIComponent(name)}?mode=${mode}`, { method: "POST" }),

  listRuns: () => request<RunSummary[]>("/api/runs"),
  getRun: (id: string) => request<RunDetail>(`/api/runs/${id}`),
  cancelRun: (id: string) => request(`/api/runs/${id}/cancel`, { method: "POST" }),
  resumeRun: (id: string) => request(`/api/runs/${id}/resume`, { method: "POST" }),
  deleteRun: (id: string) => request(`/api/runs/${id}`, { method: "DELETE" }),

  getInterview: (id: string) => request<{ status: string; questions: Question[] }>(`/api/runs/${id}/interview`),
  submitAnswers: (id: string, answers: Record<string, string>) => request(`/api/runs/${id}/interview`, json({ answers })),
  skipInterview: (id: string) => request(`/api/runs/${id}/interview/skip`, { method: "POST" }),

  getRequirements: (id: string) => request<{ data: Requirements; markdown: string }>(`/api/runs/${id}/requirements`),
  getGroundability: (id: string) => request<GroundabilityReport>(`/api/runs/${id}/groundability`),
  getAgent: (id: string) =>
    request<{ data: AgentDefinition; yaml: string; versions: { version: number; data: AgentDefinition }[] }>(
      `/api/runs/${id}/agent`,
    ),
  getEvals: (id: string) =>
    request<{ cases: EvalCase[]; rejected: EvalCase[]; stats: Record<string, unknown> }>(`/api/runs/${id}/evals`),
  getScorecards: (id: string) => request<{ scorecards: Scorecard[] }>(`/api/runs/${id}/scorecards`),
  getCase: (id: string, iteration: string, caseId: string) =>
    request<{ case: EvalCase; result: Scorecard["cases"][number]; transcript: Record<string, unknown> }>(
      `/api/runs/${id}/scorecards/${iteration}/cases/${caseId}`,
    ),
  getChangelog: (id: string) =>
    request<{ entries: ChangeEntry[]; summary: { stop_reason: string; best_version: number } | null }>(
      `/api/runs/${id}/changelog`,
    ),
  getReport: (id: string) => request<string>(`/api/runs/${id}/report`),
  downloadUrl: (id: string) => `${API_URL}/api/runs/${id}/download`,

  listAgents: () => request<AgentSummary[]>("/api/agents"),
  getAgentDef: (agentId: string) => request<{ agent_id: string; data: AgentDefinition }>(`/api/agents/${agentId}`),
  uploadAgent: (form: FormData) =>
    request<{ agent_id: string; name: string }>("/api/agents/upload", { method: "POST", body: form }, 120_000),
  chat: (agentId: string, message: string, history: { role: string; content: string }[]) =>
    request<ChatResponse>(`/api/agents/${agentId}/chat`, json({ message, history }), 180_000),
};
