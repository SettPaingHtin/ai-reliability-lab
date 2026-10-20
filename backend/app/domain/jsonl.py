"""JSONL dataset import/export with per-line validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.domain.scoring import RuleValidationError, parse_rule

MAX_LINES = 10_000
MAX_FIELD_CHARS = 50_000
_ALLOWED = {"input", "expected", "context", "rules", "metadata"}


@dataclass(frozen=True)
class CaseSpec:
    input: str
    expected: str | None = None
    context: str | None = None
    rules: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LineError:
    line: int
    message: str


@dataclass
class ParseResult:
    cases: list[CaseSpec]
    errors: list[LineError]

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_line(raw: str) -> CaseSpec:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(obj, dict):
        raise ValueError("each line must be a JSON object")
    unknown = set(obj) - _ALLOWED
    if unknown:
        raise ValueError(f"unknown fields: {sorted(unknown)}")
    text = obj.get("input")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("'input' is required and must be a non-empty string")
    for name in ("expected", "context"):
        val = obj.get(name)
        if val is not None and not isinstance(val, str):
            raise ValueError(f"'{name}' must be a string")
    for name in ("input", "expected", "context"):
        val = obj.get(name)
        if isinstance(val, str) and len(val) > MAX_FIELD_CHARS:
            raise ValueError(f"'{name}' longer than {MAX_FIELD_CHARS} characters")
    meta = obj.get("metadata", {})
    if not isinstance(meta, dict):
        raise ValueError("'metadata' must be an object")
    raw_rules = obj.get("rules", [])
    if not isinstance(raw_rules, list):
        raise ValueError("'rules' must be a list")
    try:
        rules = tuple(parse_rule(r).to_dict() for r in raw_rules)
    except RuleValidationError as exc:
        raise ValueError(f"invalid rule: {exc}") from exc
    expected = obj.get("expected")
    if not rules and expected is None:
        raise ValueError("provide 'expected' (exact match) or at least one rule")
    if any(r["type"] == "exact" and r["value"] is None for r in rules) and expected is None:
        raise ValueError("exact rule without 'value' requires 'expected'")
    return CaseSpec(input=text, expected=expected, context=obj.get("context"), rules=rules, metadata=meta)


def parse_jsonl(text: str, max_errors: int = 50) -> ParseResult:
    """Parse a JSONL document. Collects every line error (up to max_errors); blank lines are skipped."""
    cases: list[CaseSpec] = []
    errors: list[LineError] = []
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        return ParseResult([], [LineError(0, f"too many lines (max {MAX_LINES})")])
    for number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            cases.append(_parse_line(raw))
        except ValueError as exc:
            if len(errors) < max_errors:
                errors.append(LineError(number, str(exc)))
    if not cases and not errors:
        errors.append(LineError(0, "no test cases found"))
    return ParseResult(cases, errors)


def dump_jsonl(cases: Iterable[CaseSpec]) -> str:
    out = []
    for c in cases:
        row: dict[str, Any] = {"input": c.input}
        if c.expected is not None:
            row["expected"] = c.expected
        if c.context is not None:
            row["context"] = c.context
        if c.rules:
            row["rules"] = [{k: v for k, v in r.items() if v is not None} for r in c.rules]
        if c.metadata:
            row["metadata"] = c.metadata
        out.append(json.dumps(row, ensure_ascii=False))
    return "\n".join(out) + ("\n" if out else "")
