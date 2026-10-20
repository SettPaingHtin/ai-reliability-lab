"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { api, type CaseResult, type Page, type Run } from "@/lib/api";
import { formatCost, formatInt, formatMs, formatPercent } from "@/lib/format";

const PAGE_SIZE = 25;
const FILTERS = [
  { label: "Not passing", query: "&status=failed&status=error" },
  { label: "Failed", query: "&status=failed" },
  { label: "Errors", query: "&status=error" },
  { label: "Passed", query: "&status=passed" },
  { label: "All", query: "" },
] as const;

function Stat({ label, value }: { label: string; value: string }) {
  return <div className="card stat"><div className="v">{value}</div><div className="l">{label}</div></div>;
}

function ResultRow({ r }: { r: CaseResult }) {
  return (
    <details className="card" style={{ marginBottom: 8 }}>
      <summary>
        <span className={`badge ${r.status}`}>{r.status}</span>{" "}
        <strong>#{r.position + 1}</strong> {r.input_snapshot.slice(0, 90)}
        <span className="muted"> · score {r.score == null ? "—" : r.score.toFixed(2)} · {formatMs(r.latency_ms)} · {r.attempts} attempt(s)</span>
      </summary>
      <div className="cols">
        <div><div className="muted">Expected</div><pre>{r.expected_snapshot ?? "(rules only)"}</pre></div>
        <div><div className="muted">Actual output</div><pre>{r.output ?? "(no output)"}</pre></div>
      </div>
      {r.error && <div role="alert" className="alert">Execution error: {r.error}</div>}
      {r.score_details.rules && (
        <>
          <div className="muted">Deterministic checks</div>
          <ul>{r.score_details.rules.map((rule, i) => (
            <li key={i} className={rule.passed ? "passed" : "failed"}>
              {rule.passed ? "✓" : "✗"} <code>{rule.type}</code>: {rule.message}
            </li>))}
          </ul>
        </>
      )}
      <div className="muted">
        Tokens: {formatInt(r.prompt_tokens)} in / {formatInt(r.completion_tokens)} out · Cost: {formatCost(r.cost_usd)}
      </div>
    </details>
  );
}

export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [run, setRun] = useState<Run | null>(null);
  const [results, setResults] = useState<Page<CaseResult> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState(0);
  const [offset, setOffset] = useState(0);

  const loadRun = useCallback(async () => {
    try {
      setRun(await api<Run>(`/runs/${id}`));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load run");
    }
  }, [id]);

  const loadResults = useCallback(async () => {
    try {
      setResults(await api<Page<CaseResult>>(`/runs/${id}/results?limit=${PAGE_SIZE}&offset=${offset}${FILTERS[filter]!.query}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load results");
    }
  }, [id, filter, offset]);

  useEffect(() => { void loadRun(); }, [loadRun]);
  useEffect(() => { void loadResults(); }, [loadResults]);

  const active = run?.status === "queued" || run?.status === "running";
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => { void loadRun(); void loadResults(); }, 1500);
    return () => clearInterval(t);
  }, [active, loadRun, loadResults]);

  if (error && !run) return <div role="alert" className="alert">{error}</div>;
  if (!run) return <p className="muted">Loading…</p>;

  return (
    <>
      <p><Link href={`/projects/${run.project_id}`}>← Project</Link></p>
      <h1>Run <span className={`badge ${run.status}`} aria-live="polite">{run.status}</span></h1>
      <p className="muted">{run.provider}/{run.model} · {run.completed}/{run.total} cases processed</p>
      {run.status === "failed" && <div role="alert" className="alert">Run failed: {run.error_message ?? "unknown error"}</div>}
      <div className="grid">
        <Stat label="Pass rate" value={formatPercent(run.pass_rate)} />
        <Stat label="Passed" value={formatInt(run.passed)} />
        <Stat label="Failed" value={formatInt(run.failed)} />
        <Stat label="Errors" value={formatInt(run.errored)} />
        <Stat label="Avg latency" value={formatMs(run.avg_latency_ms)} />
        <Stat label="p95 latency" value={formatMs(run.p95_latency_ms)} />
        <Stat label="Tokens" value={formatInt(run.total_tokens)} />
        <Stat label="Est. cost" value={formatCost(run.total_cost_usd)} />
      </div>
      <p className="muted">— means the metric was not reported by the provider (not zero). Mock-provider costs use illustrative pricing.</p>

      <h2>Test results</h2>
      <div className="row" role="tablist" aria-label="Result filter">
        {FILTERS.map((f, i) => (
          <button key={f.label} role="tab" aria-selected={i === filter} className={i === filter ? "primary" : ""}
            onClick={() => { setFilter(i); setOffset(0); }}>{f.label}</button>
        ))}
      </div>
      <div style={{ marginTop: 12 }}>
        {results === null ? <p className="muted">Loading…</p> : results.items.length === 0 ? (
          <div className="empty">{active ? "Waiting for results…" : "No results match this filter."}</div>
        ) : results.items.map((r) => <ResultRow key={r.id} r={r} />)}
      </div>
      {results && results.total > PAGE_SIZE && (
        <div className="row">
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
          <span className="muted">{offset + 1}–{Math.min(offset + PAGE_SIZE, results.total)} of {results.total}</span>
          <button disabled={offset + PAGE_SIZE >= results.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button>
        </div>
      )}
    </>
  );
}
