import Link from "next/link";
import type { CaseResult, Project, Run } from "@/lib/api";
import { formatCost, formatDuration, formatInt, formatMs, formatPercent, initials } from "@/lib/format";
import { EmptyState, OutcomeBar, Stat, StatusBadge } from "./ui";

export function RunSummary({ run }: { run: Run }) {
  return (
    <>
      <div className="card card-pad hero">
        <div>
          <div className="hero-label">Pass rate</div>
          {run.pass_rate == null ? (
            <div className="hero-value na">{run.status === "queued" || run.status === "running" ? "In progress" : "—"}</div>
          ) : (
            <div className="hero-value">{formatPercent(run.pass_rate)}</div>
          )}
        </div>
        <OutcomeBar run={run} />
      </div>
      <div className="stats">
        <Stat label="Avg latency" value={formatMs(run.avg_latency_ms)} />
        <Stat label="p50 latency" value={formatMs(run.p50_latency_ms)} />
        <Stat label="p95 latency" value={formatMs(run.p95_latency_ms)} />
        <Stat label="Tokens" value={formatInt(run.total_tokens)} />
        <Stat label="Est. cost" value={formatCost(run.total_cost_usd)} />
        <Stat label="Duration" value={formatDuration(run.started_at, run.finished_at)} />
      </div>
      <p className="hint" style={{ marginTop: 10 }}>
        “—” means the provider did not report that metric; it is not zero. Mock-provider cost uses illustrative pricing.
      </p>
    </>
  );
}

export function ResultCard({ r }: { r: CaseResult }) {
  const rules = r.score_details.rules ?? [];
  return (
    <details className={`result result-${r.status}`}>
      <summary>
        <StatusBadge status={r.status} />
        <span className="r-index">#{r.position + 1}</span>
        <span className="r-title">{r.input_snapshot}</span>
        <span className="r-meta">
          <span>score {r.score == null ? "—" : r.score.toFixed(2)}</span>
          <span>{formatMs(r.latency_ms)}</span>
          {r.attempts > 1 && <span>{r.attempts} attempts</span>}
        </span>
      </summary>
      <div className="result-body">
        {r.context_snapshot && (
          <div style={{ marginTop: 12 }}>
            <p className="pane-label">Context</p>
            <pre>{r.context_snapshot}</pre>
          </div>
        )}
        <div className="cols">
          <div className="pane-expected">
            <p className="pane-label">Expected</p>
            {r.expected_snapshot == null ? (
              <pre className="placeholder">No exact expectation; scored by the rules below</pre>
            ) : (
              <pre>{r.expected_snapshot}</pre>
            )}
          </div>
          <div className={`pane-actual ${r.status === "passed" ? "good" : "bad"}`}>
            <p className="pane-label">Actual output</p>
            <pre>{r.output ?? "(no output)"}</pre>
          </div>
        </div>
        {r.error && (
          <div className="alert" role="alert">
            <strong>Execution error:</strong> {r.error}
          </div>
        )}
        {rules.length > 0 && (
          <>
            <p className="pane-label" style={{ marginTop: 14 }}>
              Deterministic checks
            </p>
            <ul className="checks">
              {rules.map((rule, i) => (
                <li key={i} className={rule.passed ? "check-pass" : "check-fail"}>
                  <span className="check-icon" aria-hidden="true">{rule.passed ? "✓" : "✕"}</span>
                  <span>
                    <code>{rule.type}</code> {rule.message}
                    <span className="sr-only">{rule.passed ? " (passed)" : " (failed)"}</span>
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
        <div className="kv">
          <span>Tokens <b>{formatInt(r.prompt_tokens)}</b> in / <b>{formatInt(r.completion_tokens)}</b> out</span>
          <span>Cost <b>{formatCost(r.cost_usd)}</b></span>
          <span>Latency <b>{formatMs(r.latency_ms)}</b></span>
          <span>Attempts <b>{r.attempts}</b></span>
        </div>
      </div>
    </details>
  );
}

export function ResultList({ items, active }: { items: CaseResult[]; active: boolean }) {
  if (items.length === 0) {
    return <EmptyState title={active ? "Waiting for results…" : "Nothing here"}>{active ? "Results appear as cases complete." : "No results match this filter."}</EmptyState>;
  }
  return <div className="results">{items.map((r) => <ResultCard key={r.id} r={r} />)}</div>;
}

export function RunsTable({ runs }: { runs: Run[] }) {
  if (runs.length === 0) {
    return <EmptyState title="No runs yet">Import cases, then run an evaluation.</EmptyState>;
  }
  return (
    <div className="card table-wrap">
      <table>
        <thead>
          <tr><th>Started</th><th>Status</th><th>Model</th><th className="num">Pass rate</th><th className="num">Avg latency</th><th className="num">Est. cost</th></tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id}>
              <td><Link href={`/runs/${r.id}`}>{new Date(r.created_at).toLocaleString()}</Link></td>
              <td><StatusBadge status={r.status} /></td>
              <td><span className="tag">{r.provider}/{r.model}</span></td>
              <td className="num">{formatPercent(r.pass_rate)}</td>
              <td className="num">{formatMs(r.avg_latency_ms)}</td>
              <td className="num">{formatCost(r.total_cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ProjectGrid({ projects }: { projects: Project[] }) {
  return (
    <div className="grid-cards">
      {projects.map((p) => (
        <Link key={p.id} href={`/projects/${p.id}`} className="card card-link">
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <div className="avatar" aria-hidden="true">{initials(p.name)}</div>
            <div style={{ minWidth: 0 }}>
              <strong>{p.name}</strong>
              <div className="hint">Created {new Date(p.created_at).toLocaleDateString()}</div>
            </div>
          </div>
          <p className="muted" style={{ margin: "10px 0 0" }}>{p.description ?? "No description"}</p>
        </Link>
      ))}
    </div>
  );
}
