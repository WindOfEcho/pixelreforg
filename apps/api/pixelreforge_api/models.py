from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "processing", "completed", "failed", "cancelled"]
ScaleMode = Literal["auto", "manual"]
RestoreAlgorithm = Literal["auto", "integer-grid-v1", "resampled-grid-v2", "noisy-pixel-v1", "ai-pixel-v2", "ai-grid-hypothesis-v1"]
PaletteCleanupMode = Literal["off", "light", "medium", "strong", "custom"]


class JobParameters(BaseModel):
    algorithm: RestoreAlgorithm = "auto"
    scale_mode: ScaleMode = "manual"
    scale: float | None = Field(default=4, ge=1.0, le=64.0)
    min_scale: int = Field(default=2, ge=1, le=64)
    max_scale: int = Field(default=16, ge=1, le=64)
    original_width: int | None = Field(default=None, ge=1)
    original_height: int | None = Field(default=None, ge=1)
    palette_cleanup: PaletteCleanupMode = "off"
    palette_merge_distance: float | None = Field(default=None, ge=0.0, le=128.0)
    palette_target_colors: int | None = Field(default=None, ge=1, le=256)
    noisy_color_bucket_size: int = Field(default=16, ge=2, le=64)
    confidence_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    fractional_scale_step: float = Field(default=0.25, ge=0.05, le=1.0)


class JobMetadata(BaseModel):
    job_id: str
    owner_id: str | None = None
    status: JobStatus
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    stage: str | None = None
    stage_message: str | None = None
    input_filename: str
    input_path: str
    output_path: str | None = None
    algorithm_requested: str | None = None
    algorithm_used: str | None = None
    algorithm_version: str | None = None
    source_size: tuple[int, int] | None = None
    target_size: tuple[int, int] | None = None
    original_size_override: tuple[int, int] | None = None
    scale_x: float | None = None
    scale_y: float | None = None
    scale_method: str | None = None
    confidence: float | None = None
    palette_cleanup: str | None = None
    analysis: dict | None = None
    palette: dict | None = None
    reconstruction: dict | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    last_error: str | None = None
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None
    cancel_requested: bool = False
    worker_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class JobPublicMetadata(BaseModel):
    job_id: str
    status: JobStatus
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    stage: str | None = None
    stage_message: str | None = None
    input_filename: str
    algorithm_requested: str | None = None
    algorithm_used: str | None = None
    algorithm_version: str | None = None
    source_size: tuple[int, int] | None = None
    target_size: tuple[int, int] | None = None
    original_size_override: tuple[int, int] | None = None
    scale_x: float | None = None
    scale_y: float | None = None
    scale_method: str | None = None
    confidence: float | None = None
    palette_cleanup: str | None = None
    analysis: dict | None = None
    palette: dict | None = None
    reconstruction: dict | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    last_error: str | None = None
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    expires_at: datetime | None = None
    cancel_requested: bool = False
    worker_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    status_url: str
    download_url: str


class JobListResponse(BaseModel):
    jobs: list[JobPublicMetadata]
    limit: int
    offset: int
