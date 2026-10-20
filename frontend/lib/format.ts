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
