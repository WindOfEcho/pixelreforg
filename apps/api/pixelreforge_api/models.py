from typing import Literal

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "processing", "completed", "failed", "cancelled"]
ScaleMode = Literal["auto", "manual"]


class JobMetadata(BaseModel):
    job_id: str
    status: JobStatus
    input_filename: str
    input_path: str
    output_path: str | None = None
    source_size: tuple[int, int] | None = None
    target_size: tuple[int, int] | None = None
    scale_x: int | None = None
    scale_y: int | None = None
    scale_method: str | None = None
    confidence: float | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    status_url: str
    download_url: str
