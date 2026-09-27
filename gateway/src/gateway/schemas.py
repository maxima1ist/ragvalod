"""REST request/response models for the API Gateway."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1)
    rerank_top_n: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)


class UsedChunk(BaseModel):
    id: str
    text: str
    source: str
    title: str
    section_path: str = ""
    score: float = 0.0


class GenerateResponse(BaseModel):
    answer: str
    used_chunks: list[UsedChunk]


class IngestSourceSpec(BaseModel):
    name: str
    credentials: dict[str, str] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    sources: list[IngestSourceSpec] = Field(default_factory=list)
    all_with_credentials: bool = False


class IngestResponse(BaseModel):
    job_id: str


class SourceInfo(BaseModel):
    name: str
    description: str = ""
    requires_credentials: bool = False


class ScheduleSourceSpec(BaseModel):
    name: str
    credentials: dict[str, str] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)


class UpsertScheduleRequest(BaseModel):
    schedule_id: str | None = None
    name: str = Field(min_length=1)
    cron: str = Field(min_length=1)
    enabled: bool = True
    sources: list[ScheduleSourceSpec] = Field(default_factory=list)
    all_with_credentials: bool = False


class UpsertScheduleResponse(BaseModel):
    schedule_id: str


class ScheduleInfo(BaseModel):
    schedule_id: str
    name: str
    cron: str
    enabled: bool
    source_names: list[str] = Field(default_factory=list)
    all_with_credentials: bool = False
    last_run_at: str = ""
    last_job_id: str = ""
    created_at: str = ""
    updated_at: str = ""


class RunScheduleResponse(BaseModel):
    job_id: str
