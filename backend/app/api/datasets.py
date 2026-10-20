from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.domain.jsonl import CaseSpec, dump_jsonl, parse_jsonl
from app.models import Dataset, EvalCase, Project
from app.schemas import DatasetCreate, DatasetOut, EvalCaseOut, ImportOut, Page

router = APIRouter(tags=["datasets"])


def _dataset_out(session: Session, dataset: Dataset) -> DatasetOut:
    count = session.scalar(select(func.count()).select_from(EvalCase).where(EvalCase.dataset_id == dataset.id)) or 0
    out = DatasetOut.model_validate(dataset)
    out.case_count = count
    return out


def _get_dataset(session: Session, dataset_id: str) -> Dataset:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "Dataset not found")
    return dataset


@router.post("/projects/{project_id}/datasets", response_model=DatasetOut, status_code=201)
def create_dataset(project_id: str, body: DatasetCreate, session: Session = Depends(get_session)) -> DatasetOut:
    if session.get(Project, project_id) is None:
        raise HTTPException(404, "Project not found")
    dataset = Dataset(project_id=project_id, name=body.name.strip())
    session.add(dataset)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "A dataset with this name already exists in the project") from exc
    return _dataset_out(session, dataset)


@router.get("/projects/{project_id}/datasets", response_model=Page[DatasetOut])
def list_datasets(
    project_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> Page[DatasetOut]:
    if session.get(Project, project_id) is None:
        raise HTTPException(404, "Project not found")
    total = session.scalar(select(func.count()).select_from(Dataset).where(Dataset.project_id == project_id)) or 0
    rows = session.scalars(
        select(Dataset).where(Dataset.project_id == project_id).order_by(Dataset.created_at.desc(), Dataset.id).limit(limit).offset(offset)
    )
    return Page(items=[_dataset_out(session, d) for d in rows], total=total, limit=limit, offset=offset)


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: str, session: Session = Depends(get_session)) -> DatasetOut:
    return _dataset_out(session, _get_dataset(session, dataset_id))


async def _read_limited(request: Request, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise HTTPException(413, f"Import larger than {limit} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/datasets/{dataset_id}/import", response_model=ImportOut, status_code=201)
async def import_jsonl(dataset_id: str, request: Request, session: Session = Depends(get_session)) -> ImportOut:
    """Append cases from a JSONL body (text/plain). All-or-nothing: any invalid line rejects the import."""
    dataset = _get_dataset(session, dataset_id)
    raw = await _read_limited(request, request.app.state.settings.max_import_bytes)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "Import must be UTF-8 text") from exc
    parsed = parse_jsonl(text)
    if not parsed.ok:
        raise HTTPException(
            422,
            detail={
                "message": "Dataset validation failed; nothing was imported",
                "errors": [{"line": e.line, "message": e.message} for e in parsed.errors],
            },
        )
    start = session.scalar(select(func.coalesce(func.max(EvalCase.position), -1)).where(EvalCase.dataset_id == dataset.id)) + 1
    session.add_all(
        EvalCase(
            dataset_id=dataset.id,
            position=start + i,
            input=c.input,
            expected=c.expected,
            context=c.context,
            rules=list(c.rules),
            case_metadata=c.metadata,
        )
        for i, c in enumerate(parsed.cases)
    )
    session.commit()
    return ImportOut(imported=len(parsed.cases))


@router.get("/datasets/{dataset_id}/export", response_class=PlainTextResponse)
def export_jsonl(dataset_id: str, session: Session = Depends(get_session)) -> PlainTextResponse:
    dataset = _get_dataset(session, dataset_id)
    rows = session.scalars(select(EvalCase).where(EvalCase.dataset_id == dataset.id).order_by(EvalCase.position))
    specs = [CaseSpec(r.input, r.expected, r.context, tuple(r.rules or ()), dict(r.case_metadata or {})) for r in rows]
    return PlainTextResponse(dump_jsonl(specs), media_type="application/x-ndjson")


@router.get("/datasets/{dataset_id}/cases", response_model=Page[EvalCaseOut])
def list_cases(
    dataset_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> Page[EvalCaseOut]:
    _get_dataset(session, dataset_id)
    total = session.scalar(select(func.count()).select_from(EvalCase).where(EvalCase.dataset_id == dataset_id)) or 0
    rows = session.scalars(select(EvalCase).where(EvalCase.dataset_id == dataset_id).order_by(EvalCase.position).limit(limit).offset(offset))
    return Page(items=[EvalCaseOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)
