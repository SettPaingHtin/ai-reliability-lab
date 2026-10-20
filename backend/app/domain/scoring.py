"""Deterministic scoring rules.

Model-based grading is deliberately NOT in this module: deterministic checks and AI
judgments are stored and displayed separately (see score_details["kind"]).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

RULE_TYPES = ("exact", "contains", "not_contains", "regex")
MAX_OUTPUT_CHARS = 20_000  # outputs are untrusted; bound the work any rule can do
MAX_PATTERN_CHARS = 200
_ALLOWED_FIELDS = {"type", "value", "case_sensitive", "strip"}


class RuleValidationError(ValueError):
    """A scoring rule definition is malformed."""


@dataclass(frozen=True)
class Rule:
    type: str
    value: str | None = None
    case_sensitive: bool = True
    strip: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "value": self.value,
            "case_sensitive": self.case_sensitive,
            "strip": self.strip,
        }


@dataclass(frozen=True)
class RuleResult:
    type: str
    passed: bool
    score: float
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "passed": self.passed, "score": self.score, "message": self.message}


@dataclass(frozen=True)
class CaseScore:
    passed: bool
    score: float
    rule_results: tuple[RuleResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "deterministic", "rules": [r.to_dict() for r in self.rule_results]}


def parse_rule(raw: Any) -> Rule:
    """Validate a raw rule dict and return a normalized Rule."""
    if not isinstance(raw, dict):
        raise RuleValidationError("rule must be an object")
    unknown = set(raw) - _ALLOWED_FIELDS
    if unknown:
        raise RuleValidationError(f"unknown rule fields: {sorted(unknown)}")
    rtype = raw.get("type")
    if rtype not in RULE_TYPES:
        raise RuleValidationError(f"rule type must be one of {list(RULE_TYPES)}")
    value = raw.get("value")
    if value is not None and not isinstance(value, str):
        raise RuleValidationError("rule value must be a string")
    for flag in ("case_sensitive", "strip"):
        if flag in raw and not isinstance(raw[flag], bool):
            raise RuleValidationError(f"{flag} must be a boolean")
    if rtype in ("contains", "not_contains", "regex") and not value:
        raise RuleValidationError(f"rule type '{rtype}' requires a non-empty value")
    if rtype == "regex":
        assert value is not None
        if len(value) > MAX_PATTERN_CHARS:
            raise RuleValidationError(f"regex pattern longer than {MAX_PATTERN_CHARS} characters")
        try:
            re.compile(value)
        except re.error as exc:
            raise RuleValidationError(f"invalid regex: {exc}") from exc
    return Rule(
        type=rtype,
        value=value,
        case_sensitive=raw.get("case_sensitive", True),
        strip=raw.get("strip", True),
    )


def _clip(text: str, limit: int = 120) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _normalize(text: str, rule: Rule) -> str:
    if rule.strip:
        text = text.strip()
    if not rule.case_sensitive:
        text = text.lower()
    return text


def _apply_rule(output: str, rule: Rule, expected: str | None) -> RuleResult:
    target = rule.value if rule.value is not None else expected
    if rule.type == "exact":
        if target is None:
            return RuleResult("exact", False, 0.0, "no expected value configured for exact match")
        ok = _normalize(output, rule) == _normalize(target, rule)
        msg = "output matches expected exactly" if ok else (
            f"expected {_clip(repr(target))} but got {_clip(repr(output))}"
        )
        return RuleResult("exact", ok, 1.0 if ok else 0.0, msg)
    if target is None:
        return RuleResult(rule.type, False, 0.0, f"no value configured for {rule.type}")
    if rule.type == "contains":
        ok = _normalize(target, rule) in _normalize(output, rule)
        msg = f"output contains {_clip(repr(target))}" if ok else (
            f"output should contain {_clip(repr(target))} but it is missing"
        )
        return RuleResult("contains", ok, 1.0 if ok else 0.0, msg)
    if rule.type == "not_contains":
        found = _normalize(target, rule) in _normalize(output, rule)
        ok = not found
        msg = f"output does not contain {_clip(repr(target))}" if ok else (
            f"output should not contain {_clip(repr(target))} but it was found"
        )
        return RuleResult("not_contains", ok, 1.0 if ok else 0.0, msg)
    if rule.type == "regex":
        flags = 0 if rule.case_sensitive else re.IGNORECASE
        ok = re.search(target, output, flags) is not None
        msg = f"output matches /{target}/" if ok else f"output does not match /{target}/"
        return RuleResult("regex", ok, 1.0 if ok else 0.0, msg)
    raise RuleValidationError(f"unsupported rule type {rule.type!r}")


def score_output(output: str, rules: list[Rule], expected: str | None) -> CaseScore:
    """Score one output. Case passes only if every rule passes; score is the mean rule score.

    With no rules, falls back to an exact match against `expected`.
    """
    if not rules:
        if expected is None:
            raise ValueError("cannot score: no rules and no expected output")
        rules = [Rule("exact")]
    bounded = output[:MAX_OUTPUT_CHARS]
    results = tuple(_apply_rule(bounded, rule, expected) for rule in rules)
    return CaseScore(
        passed=all(r.passed for r in results),
        score=sum(r.score for r in results) / len(results),
        rule_results=results,
    )
