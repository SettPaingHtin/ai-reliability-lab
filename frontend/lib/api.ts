export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}
export interface Dataset {
  id: string;
  project_id: string;
  name: string;
  created_at: string;
  case_count: number;
}
export type RunStatus = "queued" | "running" | "completed" | "failed";
export interface Run {
  id: string;
  project_id: string;
  dataset_id: string;
  status: RunStatus;
  provider: string;
  model: string;
  total: number;
  completed: number;
  passed: number | null;
  failed: number | null;
  errored: number | null;
  pass_rate: number | null;
  avg_latency_ms: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  total_tokens: number | null;
  total_cost_usd: number | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}
export type ResultStatus = "passed" | "failed" | "error";
export interface RuleResult {
  type: string;
  passed: boolean;
  score: number;
  message: string;
}
export interface CaseResult {
  id: string;
  position: number;
  status: ResultStatus;
  input_snapshot: string;
  expected_snapshot: string | null;
  context_snapshot: string | null;
  output: string | null;
  score: number | null;
  score_details: { kind?: string; rules?: RuleResult[] };
  latency_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  cost_usd: number | null;
  attempts: number;
  error: string | null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public lineErrors: { line: number; message: string }[] = [],
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { cache: "no-store", ...init });
  if (res.status === 204) return undefined as T;
  const isJson = res.headers.get("content-type")?.includes("json");
  const body: unknown = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") throw new ApiError(detail, res.status);
    if (detail && typeof detail === "object" && "message" in detail) {
      const d = detail as { message: string; errors?: { line: number; message: string }[] };
      throw new ApiError(d.message, res.status, d.errors ?? []);
    }
    if (Array.isArray(detail)) throw new ApiError("Invalid request", res.status);
    throw new ApiError(`Request failed (${res.status})`, res.status);
  }
  return body as T;
}

export const postJson = <T,>(path: string, data: unknown) =>
  api<T>(path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(data) });
