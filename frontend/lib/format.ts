// Unavailable metrics (null/undefined) render as an em dash; a measured zero renders as 0.
export const UNAVAILABLE = "—";

export function formatPercent(value: number | null | undefined): string {
  return value == null ? UNAVAILABLE : `${(value * 100).toFixed(1)}%`;
}

export function formatMs(value: number | null | undefined): string {
  return value == null ? UNAVAILABLE : `${value.toFixed(0)} ms`;
}

export function formatInt(value: number | null | undefined): string {
  return value == null ? UNAVAILABLE : value.toLocaleString("en-US");
}

export function formatCost(value: number | null | undefined): string {
  if (value == null) return UNAVAILABLE;
  return value === 0 ? "$0.00" : value < 0.01 ? `$${value.toFixed(6)}` : `$${value.toFixed(2)}`;
}

export function formatDuration(startIso: string | null | undefined, endIso: string | null | undefined): string {
  if (!startIso || !endIso) return UNAVAILABLE;
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return UNAVAILABLE;
  if (ms < 1000) return `${ms} ms`;
  const s = ms / 1000;
  return s < 60 ? `${s.toFixed(1)} s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export function initials(name: string): string {
  const parts = name.trim().split(/[\s_-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase();
}
