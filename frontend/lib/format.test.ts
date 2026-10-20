import { describe, expect, it } from "vitest";
import { formatCost, formatDuration, formatInt, formatMs, formatPercent, initials, UNAVAILABLE } from "./format";

describe("format helpers", () => {
  it("renders null and undefined as unavailable", () => {
    for (const fn of [formatPercent, formatMs, formatInt, formatCost]) {
      expect(fn(null)).toBe(UNAVAILABLE);
      expect(fn(undefined)).toBe(UNAVAILABLE);
    }
  });

  it("renders measured zero as a value, not as unavailable", () => {
    expect(formatPercent(0)).toBe("0.0%");
    expect(formatMs(0)).toBe("0 ms");
    expect(formatInt(0)).toBe("0");
    expect(formatCost(0)).toBe("$0.00");
  });

  it("formats typical values", () => {
    expect(formatPercent(2 / 3)).toBe("66.7%");
    expect(formatMs(41.6)).toBe("42 ms");
    expect(formatInt(12345)).toBe("12,345");
    expect(formatCost(0.0004)).toBe("$0.000400");
    expect(formatCost(1.234)).toBe("$1.23");
  });

  it("formats durations and handles missing timestamps", () => {
    expect(formatDuration(null, "2026-01-01T00:00:01Z")).toBe(UNAVAILABLE);
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:00:00.250Z")).toBe("250 ms");
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:00:12.5Z")).toBe("12.5 s");
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:02:05Z")).toBe("2m 5s");
    expect(formatDuration("2026-01-01T00:00:05Z", "2026-01-01T00:00:00Z")).toBe(UNAVAILABLE);
  });

  it("builds initials", () => {
    expect(initials("Support Bot")).toBe("SB");
    expect(initials("rag-eval")).toBe("RE");
    expect(initials("  ")).toBe("?");
  });
});
