// TypeScript mirrors of the backend Pydantic schemas (backend/forge/schemas). Keep in sync.

export const STAGES = [
  "ingest",
  "intake",
  "guard",
  "generate_agent",
  "generate_evals",
  "evaluate_0",
  "optimize",
  "final_holdout",
  "report",
] as const; // must equal forge/pipeline.py STAGES

export type StageName = (typeof STAGES)[number];
export type RunStatus =
  | "queued"
  | "running"
  | "awaiting_answers"
  | "completed"
  | "failed"
  | "budget_stopped"
  | "cancelled"
  | "uploaded"
  | "unknown";
export type StageStatus = "pending" | "running" | "done" | "failed" | "skipped" | "waiting";

export interface Stage {
  name: StageName;
  status: StageStatus;
  message: string;
  started_at: number | null;
  finished_at: number | null;
}

export interface RunSummary {
  run_id: string;
  created_at: number | null;
  brief_preview: string;
  status: RunStatus;
  source: string;
  final_pass_rate: number | null;
  holdout_pass_rate: number | null;
  agent_name: string | null;
}

export interface RunDetail {
  run_id: string;
  brief: string;
  mode: string | null;
  source: string | null;
  created_at: number | null;
  status: RunStatus;
  current_stage: StageName | null;
  error: string | null;
  notes: string[];
  queue_position: number | null;
  stages: Stage[];
  available: Record<"requirements" | "groundability" | "agent" | "evals" | "scorecards" | "changelog" | "report", boolean>;
}

export interface Question {
  id: string;
  field_path: string;
  text: string;
  why: string;
  kind: "yes_no" | "choice" | "free_text";
  options: string[];
  default: string;
}

export interface MustAnswer { id: string; topic: string; example_question: string; priority: number }
export interface MustRefuse { id: string; topic: string; reason: string; source: string }
export interface InterviewTurn {
  question_id: string; field_path: string; question: string; why_asked: string; answer: string; source: string;
}
export interface Requirements {
  run_id: string;
  brief: string;
  agent_name: string;
  scope: { in_scope: string[]; out_of_scope: string[] };
  audience: { who: string; expertise: string };
  tone: { style: string; formality: string; language: string };
  must_answer: MustAnswer[];
  must_refuse: MustRefuse[];
  output_preferences: { format: string; max_words: number; citations_required: boolean };
  interview: InterviewTurn[];
  assumptions: string[];
}

export interface Probe {
  question: string;
  retrieved: { chunk_id: string; score: number }[];
  supporting_quote: string | null;
  supporting_chunk_id: string | null;
  quote_verified: boolean;
  llm_said_supported: boolean;
}
export interface AskVerdict {
  ask_id: string;
  ask_text: string;
  source: string;
  verdict: "supported" | "partial" | "unsupported" | "needs_tool";
  needed_tool: string | null;
  probes: Probe[];
  explanation: string;
}
export interface GroundabilityReport {
  verdicts: AskVerdict[];
  moved_to_refuse: string[];
  warnings: string[];
  coverage: number;
}

export interface ToolBinding { name: string; reason: string; config: Record<string, unknown> }
export interface AgentDefinition {
  schema_version: number;
  name: string;
  version: number;
  description: string;
  model: { provider: string; name: string; temperature: number; seed: number; max_tokens: number };
  system_prompt: { slots: Record<string, string>; few_shots: { q: string; a: string }[]; rendered: string };
  corpus: { docs_dir: string; index_dir: string; tables: { name: string; path: string }[] };
  retrieval: {
    chunk_size: number; chunk_overlap: number; embedder: string; mode: string; bm25_weight: number; top_k: number;
    rerank: boolean; min_score: number; query_rewrite: boolean; reasons: string[];
  };
  tools: ToolBinding[];
  output_contract: { json_schema_ref: string; require_citations: boolean; max_words: number };
  refusal_message: string;
  suggested_questions: string[];
}

export interface KeyFact { fact: string; kind: string; value: string | number | null }
export interface SourceRef { doc_id: string; page: number | null; chunk_id: string; quote: string }
export interface EvalCase {
  id: string;
  category: "answerable" | "multi_doc" | "tool" | "must_refuse" | "ambiguous" | "edge";
  split: "train" | "holdout";
  question: string;
  expected_behavior: "answer" | "refuse" | "clarify";
  key_facts: KeyFact[];
  sources: SourceRef[];
  expected_tools: string[];
  gold_answer: string | null;
  notes: string;
  generation: { prompt_id: string; prompt_version: number; validated: boolean; repairs: string[]; rejected_reason: string | null };
}

export interface DeterministicResult {
  schema_valid: boolean; citation_exists: boolean; citation_quote_verbatim: boolean; key_fact_coverage: number | null;
  numbers_grounded: boolean; refusal_correct: boolean; clarify_correct: boolean | null; tool_correct: boolean;
  length_ok: boolean; hard_fail: boolean; details: Record<string, unknown>;
}
export interface JudgeResult {
  faithfulness: number | null; relevance: number | null; tone: number | null; ambiguity_handling: number | null;
  rationale: string; judge_model: string; skipped: boolean;
}
export interface CaseResult {
  case_id: string; category: string; split: string; verdict: "pass" | "fail"; deterministic: DeterministicResult;
  judge: JudgeResult; failure_class: string | null; failure_reason: string; retrieved_chunk_ids: string[];
  gold_in_topk: boolean | null; latency_ms: number; tokens: number;
}
export interface Summary {
  n_cases: number; pass_rate: number; mean_judge: number | null; key_fact_coverage: number | null;
  hallucination_rate: number; refusal_precision: number | null; refusal_recall: number | null;
  by_category: Record<string, number>;
}
export interface JudgeReliability {
  calibration_pass: boolean | null; calibration_passed: number; calibration_total: number;
  calibration_details: { case: string; item: string; expect: string; got: unknown; passed: boolean }[];
  flip_agreement: number | null; judge_det_disagreement: number | null;
}
export interface Scorecard {
  iteration: string; run_id: string; agent_version: number; split_scored: string; summary: Summary;
  judge_reliability: JudgeReliability; cases: CaseResult[];
}

export interface FieldChange { path: string; before: unknown; after: unknown; text_diff: string | null }
export interface ChangeEntry {
  iteration: number; timestamp: string; failure_class: string; target_case_ids: string[]; hypothesis: string;
  changes: FieldChange[]; score_before: { overall: number; by_category: Record<string, number> };
  score_after: { overall: number; by_category: Record<string, number> }; kept: boolean; reverted_reason: string | null;
  agent_version_before: number; agent_version_after: number;
}

export interface Citation { doc_id: string; page: number | null; chunk_id: string | null; quote: string }
export interface ToolCallRecord { tool: string; arguments: Record<string, unknown>; result: unknown; error: string | null }
export interface AgentAnswer {
  answer: string; citations: Citation[]; tool_calls: ToolCallRecord[]; refused: boolean; refusal_reason: string | null;
  clarifying_question: string | null; confidence: number;
}
export interface ChatHit { chunk_id: string; doc_id: string; page: number; score: number; dense: number; bm25: number; text: string }
export interface ChatResponse extends AgentAnswer {
  latency_ms: number | null;
  trace: { hits: ChatHit[]; best_score: number | null; deterministic_refusal: boolean; invalid_citations: unknown[] };
}

export interface AgentSummary {
  agent_id: string; name: string; version: number; description: string; tools: string[]; source_run: string;
  source: string | null; pass_rate: number | null; holdout_pass_rate: number | null; suggested_questions: string[];
}

export interface Health {
  status: "ok" | "degraded"; version: string; checks: Record<string, { ok: boolean; detail: string }>;
}
