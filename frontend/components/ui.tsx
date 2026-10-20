import type { ReactNode } from "react";
import type { Run } from "@/lib/api";
import { UNAVAILABLE } from "@/lib/format";

export function StatusBadge({ status }: { status: string }) {
  const label = status === "error" ? "error" : status;
  return (
    <span className={`badge badge-${status}`}>
      <span className="dot" aria-hidden="true" />
      {label}
    </span>
  );
}

export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card stat">
      <div className="l">{label}</div>
      <div className={`v${value === UNAVAILABLE ? " na" : ""}`}>{value}</div>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
        <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z" />
      </svg>
      <strong>{title}</strong>
      {children}
    </div>
  );
}

export function SkeletonRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="card card-pad" aria-busy="true" aria-label="Loading">
      <div style={{ display: "grid", gap: 14 }}>
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="skeleton" style={{ width: `${90 - i * 18}%` }} />
        ))}
      </div>
    </div>
  );
}

/** Stacked passed/failed/error bar for a finished run; a progress bar while it is still running. */
export function OutcomeBar({ run }: { run: Run }) {
  const total = run.total || 1;
  if (run.passed == null) {
    const pct = Math.min(100, Math.round((run.completed / total) * 100));
    return (
      <div>
        <div className="bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Run progress">
          <span className="bar-progress" style={{ width: `${pct}%` }} />
        </div>
        <div className="legend">
          <span><b>{run.completed}</b> of <b>{run.total}</b> cases processed</span>
        </div>
      </div>
    );
  }
  const parts = [
    { key: "passed", label: "Passed", n: run.passed, color: "var(--ok)" },
    { key: "failed", label: "Failed", n: run.failed ?? 0, color: "var(--bad)" },
    { key: "error", label: "Errors", n: run.errored ?? 0, color: "var(--warn)" },
  ] as const;
  return (
    <div>
      <div className="bar" role="img" aria-label={parts.map((p) => `${p.n} ${p.label.toLowerCase()}`).join(", ")}>
        {parts.map((p) => (
          <span key={p.key} className={`seg-${p.key}`} style={{ width: `${(p.n / total) * 100}%` }} title={`${p.label}: ${p.n}`} />
        ))}
      </div>
      <div className="legend">
        {parts.map((p) => (
          <span key={p.key}><i style={{ background: p.color }} />{p.label} <b>{p.n}</b></span>
        ))}
      </div>
    </div>
  );
}
