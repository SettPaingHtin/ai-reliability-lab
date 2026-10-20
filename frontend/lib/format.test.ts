import { describe, expect, it } from "vitest";
import { formatCost, formatInt, formatMs, formatPercent, UNAVAILABLE } from "./format";

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
});
