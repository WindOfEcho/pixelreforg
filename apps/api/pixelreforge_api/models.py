from typing import Literal

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "processing", "completed", "failed", "cancelled"]
ScaleMode = Literal["auto", "manual"]
RestoreAlgorithm = Literal["auto", "integer-grid-v1", "resampled-grid-v2", "noisy-pixel-v1"]
PaletteCleanupMode = Literal["off", "light", "medium", "strong", "custom"]


class JobMetadata(BaseModel):
    job_id: str
    status: JobStatus
    input_filename: str
    input_path: str
    output_path: str | None = None
    algorithm_requested: str | None = None
    algorithm_used: str | None = None
    algorithm_version: str | None = None
    source_size: tuple[int, int] | None = None
    target_size: tuple[int, int] | None = None
    original_size_override: tuple[int, int] | None = None
    scale_x: int | None = None
    scale_y: int | None = None
    scale_method: str | None = None
    confidence: float | None = None
    palette_cleanup: str | None = None
    analysis: dict | None = None
    palette: dict | None = None
    reconstruction: dict | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    status_url: str
    download_url: str
