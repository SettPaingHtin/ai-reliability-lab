"""Run lifecycle: create, claim (duplicate-safe), execute, finalize.

DB sessions are never held open during provider calls. Each result is committed as it
completes, so a crash leaves a resumable partial run instead of losing everything.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.domain.engine import CaseInput, EngineConfig, iter_outcomes, summarize
from app.domain.providers import build_provider
from app.models import Dataset, EvalCase, Result, Run

log = logging.getLogger("arl.runs")


def create_run(session: Session, dataset: Dataset, provider: str, model: str, engine_cfg: dict) -> Run:
    total = session.scalar(select(func.count()).select_from(EvalCase).where(EvalCase.dataset_id == dataset.id))
    if not total:
        raise ValueError("dataset has no test cases")
    run = Run(
        project_id=dataset.project_id,
        dataset_id=dataset.id,
        provider=provider,
        model=model,
        config={"engine": engine_cfg},
        total=total,
    )
    session.add(run)
    session.commit()
    return run


def claim_run(session: Session, run_id: str) -> bool:
    """Atomically move queued -> running. Exactly one concurrent caller gets True."""
    res = session.execute(
        update(Run).where(Run.id == run_id, Run.status == "queued").values(status="running", started_at=datetime.now(UTC))
    )
    session.commit()
    return res.rowcount == 1


def _fail_run(session_factory: sessionmaker[Session], run_id: str, message: str) -> None:
    with session_factory() as s:
        s.execute(
            update(Run).where(Run.id == run_id).values(status="failed", error_message=message[:500], finished_at=datetime.now(UTC))
        )
        s.commit()


def execute_run(session_factory: sessionmaker[Session], run_id: str, settings: Settings) -> None:
    with session_factory() as s:
        if not claim_run(s, run_id):
            log.info("run %s already claimed; skipping duplicate execution", run_id)
            return
        run = s.get(Run, run_id)
        assert run is not None
        try:
            cfg = EngineConfig(**run.config.get("engine", {}))
            provider = build_provider(run.provider, run.model, simulate_latency=settings.mock_simulate_latency)
        except ValueError as exc:
            _fail_run(session_factory, run_id, f"invalid run configuration: {exc}")
            return
        done = set(s.scalars(select(Result.case_id).where(Result.run_id == run_id)))
        cases = list(s.scalars(select(EvalCase).where(EvalCase.dataset_id == run.dataset_id).order_by(EvalCase.position)))
        pending = [c for c in cases if c.id not in done]
        by_id = {c.id: c for c in pending}
        inputs = [
            CaseInput(c.id, c.input, c.expected, c.context, tuple(c.rules or ()), dict(c.case_metadata or {}))
            for c in pending
        ]

    try:
        for outcome in iter_outcomes(inputs, provider, cfg):
            case = by_id[outcome.key]
            with session_factory() as s:
                s.add(
                    Result(
                        run_id=run_id,
                        case_id=case.id,
                        position=case.position,
                        status=outcome.status,
                        input_snapshot=case.input,
                        expected_snapshot=case.expected,
                        context_snapshot=case.context,
                        rules_snapshot=list(case.rules or []),
                        output=outcome.output,
                        score=outcome.score,
                        score_details=outcome.score_details,
                        latency_ms=outcome.latency_ms,
                        prompt_tokens=outcome.prompt_tokens,
                        completion_tokens=outcome.completion_tokens,
                        cost_usd=outcome.cost_usd,
                        attempts=outcome.attempts,
                        error=outcome.error,
                    )
                )
                s.commit()
        finalize_run(session_factory, run_id)
    except Exception:
        log.exception("run %s crashed", run_id)  # traceback stays in logs, not in the API response
        _fail_run(session_factory, run_id, "internal error during execution")


def finalize_run(session_factory: sessionmaker[Session], run_id: str) -> None:
    with session_factory() as s:
        rows = list(s.scalars(select(Result).where(Result.run_id == run_id)))
        summary = summarize(rows)
        s.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(
                status="completed",
                finished_at=datetime.now(UTC),
                passed=summary.passed,
                failed=summary.failed,
                errored=summary.errored,
                pass_rate=summary.pass_rate,
                avg_latency_ms=summary.avg_latency_ms,
                p50_latency_ms=summary.p50_latency_ms,
                p95_latency_ms=summary.p95_latency_ms,
                total_tokens=summary.total_tokens,
                total_cost_usd=summary.total_cost_usd,
            )
        )
        s.commit()
