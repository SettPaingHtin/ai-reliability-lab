from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models import Project
from app.schemas import Page, ProjectCreate, ProjectOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, session: Session = Depends(get_session)) -> Project:
    project = Project(name=body.name.strip(), description=body.description)
    session.add(project)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "A project with this name already exists") from exc
    return project


@router.get("", response_model=Page[ProjectOut])
def list_projects(
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), session: Session = Depends(get_session)
) -> Page[ProjectOut]:
    total = session.scalar(select(func.count()).select_from(Project)) or 0
    rows = session.scalars(select(Project).order_by(Project.created_at.desc(), Project.id).limit(limit).offset(offset))
    return Page(items=[ProjectOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, session: Session = Depends(get_session)) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, session: Session = Depends(get_session)) -> Response:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "Project not found")
    session.delete(project)  # datasets, cases, runs, results go via ON DELETE CASCADE
    session.commit()
    return Response(status_code=204)
