from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str | None
    created_at: datetime


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    name: str
    created_at: datetime
    case_count: int = 0


class EvalCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    position: int
    input: str
    expected: str | None
    context: str | None
    rules: list[dict[str, Any]]


class ImportOut(BaseModel):
    imported: int


class EngineSettings(BaseModel):
    concurrency: int = Field(default=4, ge=1, le=64)
    timeout_s: float = Field(default=30.0, gt=0, le=300)
    max_retries: int = Field(default=2, ge=0, le=5)
    backoff_base_s: float = Field(default=0.5, ge=0, le=30)
    requests_per_second: float | None = Field(default=None, gt=0)


class RunCreate(BaseModel):
    provider: str = Field(default="mock", max_length=50)
    model: str = Field(default="mock-1", min_length=1, max_length=100)
    engine: EngineSettings = Field(default_factory=EngineSettings)


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    dataset_id: str
    status: str
    provider: str
    model: str
    config: dict[str, Any]
    total: int
    completed: int = 0  # results persisted so far (progress while running)
    passed: int | None
    failed: int | None
    errored: int | None
    pass_rate: float | None
    avg_latency_ms: float | None
    p50_latency_ms: float | None
    p95_latency_ms: float | None
    total_tokens: int | None
    total_cost_usd: float | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str | None
    position: int
    status: str
    input_snapshot: str
    expected_snapshot: str | None
    context_snapshot: str | None
    output: str | None
    score: float | None
    score_details: dict[str, Any]
    latency_ms: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None
    attempts: int
    error: str | None
