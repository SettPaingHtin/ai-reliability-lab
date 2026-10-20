"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { ResultList, RunSummary } from "@/components/run-view";
import { SkeletonRows, StatusBadge } from "@/components/ui";
import { api, type CaseResult, type Page, type Run } from "@/lib/api";

const PAGE_SIZE = 25;

function filtersFor(run: Run) {
  const known = run.passed != null;
  return [
    { label: "Not passing", query: "&status=failed&status=error", count: known ? (run.failed ?? 0) + (run.errored ?? 0) : null },
    { label: "Failed", query: "&status=failed", count: known ? run.failed : null },
    { label: "Errors", query: "&status=error", count: known ? run.errored : null },
    { label: "Passed", query: "&status=passed", count: known ? run.passed : null },
    { label: "All", query: "", count: known ? run.total : null },
  ];
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

  const query = run ? filtersFor(run)[filter]!.query : "";
  const loadResults = useCallback(async () => {
    try {
      setResults(await api<Page<CaseResult>>(`/runs/${id}/results?limit=${PAGE_SIZE}&offset=${offset}${query}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load results");
    }
  }, [id, offset, query]);

  useEffect(() => { void loadRun(); }, [loadRun]);
  useEffect(() => { if (run) void loadResults(); }, [run?.id, loadResults]); // eslint-disable-line react-hooks/exhaustive-deps

  const active = run?.status === "queued" || run?.status === "running";
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => { void loadRun(); void loadResults(); }, 1500);
    return () => clearInterval(t);
  }, [active, loadRun, loadResults]);

  if (error && !run) return <div role="alert" className="alert">{error}</div>;
  if (!run) return <SkeletonRows rows={4} />;

  const filters = filtersFor(run);
  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumbs"><Link href={`/projects/${run.project_id}`}>Project</Link> / Run {run.id.slice(0, 8)}</div>
          <h1>Evaluation run <span aria-live="polite"><StatusBadge status={run.status} /></span></h1>
          <p className="sub">{run.provider}/{run.model} · started {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}</p>
        </div>
      </div>

      {run.status === "failed" && <div role="alert" className="alert">Run failed: {run.error_message ?? "unknown error"}</div>}
      <RunSummary run={run} />

      <div className="section">
        <div className="section-head">
          <h2>Test results</h2>
          <div className="tabs" role="tablist" aria-label="Result filter">
            {filters.map((f, i) => (
              <button key={f.label} role="tab" aria-selected={i === filter} className="tab" onClick={() => { setFilter(i); setOffset(0); }}>
                {f.label}{f.count != null && <span className="count">{f.count}</span>}
              </button>
            ))}
          </div>
        </div>
        {results === null ? <SkeletonRows rows={3} /> : <ResultList items={results.items} active={active} />}
        {results && results.total > PAGE_SIZE && (
          <div className="pager">
            <button className="btn btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
            <span className="hint">{offset + 1}–{Math.min(offset + PAGE_SIZE, results.total)} of {results.total}</span>
            <button className="btn btn-sm" disabled={offset + PAGE_SIZE >= results.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button>
          </div>
        )}
      </div>
    </>
  );
}
