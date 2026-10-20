from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.domain.providers import provider_names
from app.models import Dataset, Project, Result, Run
from app.schemas import Page, ResultOut, RunCreate, RunOut
from app.services.runs import create_run, execute_run

router = APIRouter(tags=["runs"])


def _run_out(session: Session, run: Run) -> RunOut:
    out = RunOut.model_validate(run)
    out.completed = session.scalar(select(func.count()).select_from(Result).where(Result.run_id == run.id)) or 0
    return out


@router.post("/datasets/{dataset_id}/runs", response_model=RunOut, status_code=202)
def start_run(
    dataset_id: str,
    body: RunCreate,
    request: Request,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
) -> RunOut:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "Dataset not found")
    if body.provider not in provider_names():
        raise HTTPException(422, f"Unknown provider; available: {provider_names()}")
    try:
        run = create_run(session, dataset, body.provider, body.model, body.engine.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    state = request.app.state
    out = _run_out(session, run)
    session.close()  # release any read lock before the background task starts writing
    background.add_task(execute_run, state.session_factory, run.id, state.settings)
    return out


@router.get("/projects/{project_id}/runs", response_model=Page[RunOut])
def list_runs(
    project_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> Page[RunOut]:
    if session.get(Project, project_id) is None:
        raise HTTPException(404, "Project not found")
    total = session.scalar(select(func.count()).select_from(Run).where(Run.project_id == project_id)) or 0
    rows = session.scalars(
        select(Run).where(Run.project_id == project_id).order_by(Run.created_at.desc(), Run.id).limit(limit).offset(offset)
    )
    return Page(items=[_run_out(session, r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, session: Session = Depends(get_session)) -> RunOut:
    run = session.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return _run_out(session, run)


@router.get("/runs/{run_id}/results", response_model=Page[ResultOut])
def list_results(
    run_id: str,
    status: list[Literal["passed", "failed", "error"]] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> Page[ResultOut]:
    if session.get(Run, run_id) is None:
        raise HTTPException(404, "Run not found")
    where = [Result.run_id == run_id]
    if status:
        where.append(Result.status.in_(status))
    total = session.scalar(select(func.count()).select_from(Result).where(*where)) or 0
    rows = session.scalars(select(Result).where(*where).order_by(Result.position).limit(limit).offset(offset))
    return Page(items=[ResultOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)
