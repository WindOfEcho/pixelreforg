from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


JobStatus = Literal["queued", "processing", "completed", "failed", "cancelled"]
JobType = Literal["restore", "sprite_sheet"]
ScaleMode = Literal["auto", "manual"]
RestoreAlgorithm = Literal[
    "auto",
    "integer-grid-v1",
    "resampled-grid-v2",
    "noisy-pixel-v1",
    "ai-pixel-v2",
    "ai-grid-hypothesis-v1",
]
PaletteCleanupMode = Literal["off", "light", "medium", "strong", "custom"]
SpriteSheetInputMode = Literal["files", "sheet"]
SpriteSheetPackingMode = Literal["compact", "grid"]
SpriteSheetSortMode = Literal["input", "name", "width", "height", "area"]
SheetExtractionMode = Literal["auto", "grid"]


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


class SpriteSheetParameters(BaseModel):
    input_mode: SpriteSheetInputMode = "files"
    packing_mode: SpriteSheetPackingMode = "compact"
    trim_transparent: bool = True
    alpha_threshold: int = Field(default=0, ge=0, le=255)
    padding: int = Field(default=1, ge=0, le=64)
    border_padding: int = Field(default=0, ge=0, le=64)
    extrude: int = Field(default=0, ge=0, le=64)
    max_width: int = Field(default=2048, ge=1, le=8192)
    max_height: int = Field(default=2048, ge=1, le=8192)
    max_atlas_pixels: int = Field(default=16_000_000, ge=1)
    atlas_width: int | None = Field(default=None, ge=1, le=8192)
    atlas_height: int | None = Field(default=None, ge=1, le=8192)
    power_of_two: bool = False
    force_square: bool = False
    allow_rotation: bool = False
    sort_mode: SpriteSheetSortMode = "area"
    grid_columns: int | None = Field(default=None, ge=1, le=512)
    background_color: str | None = None
    include_metadata: bool = True
    extraction_mode: SheetExtractionMode = "auto"
    cell_width: int | None = Field(default=None, ge=1, le=8192)
    cell_height: int | None = Field(default=None, ge=1, le=8192)
    columns: int | None = Field(default=None, ge=1, le=512)
    rows: int | None = Field(default=None, ge=1, le=512)
    offset_x: int = Field(default=0, ge=0, le=8192)
    offset_y: int = Field(default=0, ge=0, le=8192)
    gap_x: int = Field(default=0, ge=0, le=8192)
    gap_y: int = Field(default=0, ge=0, le=8192)
    max_frames: int = Field(default=4096, ge=1)

    @field_validator("background_color")
    @classmethod
    def validate_background_color(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        if not normalized.startswith("#") or len(normalized) not in (7, 9):
            raise ValueError("background_color must be #RRGGBB or #RRGGBBAA.")
        try:
            int(normalized[1:], 16)
        except ValueError as exc:
            raise ValueError("background_color must be hexadecimal.") from exc
        return normalized.upper()

    @model_validator(mode="after")
    def validate_dimensions(self) -> "SpriteSheetParameters":
        if (self.atlas_width is None) != (self.atlas_height is None):
            raise ValueError("atlas_width and atlas_height must be supplied together.")
        if self.atlas_width is not None and self.atlas_height is not None:
            if self.atlas_width > self.max_width or self.atlas_height > self.max_height:
                raise ValueError(
                    "Fixed atlas dimensions cannot exceed the maximum dimensions."
                )
            if self.force_square and self.atlas_width != self.atlas_height:
                raise ValueError("Square output requires equal fixed atlas dimensions.")
            if self.power_of_two and (
                not _is_power_of_two(self.atlas_width)
                or not _is_power_of_two(self.atlas_height)
            ):
                raise ValueError(
                    "Power-of-two output requires power-of-two fixed dimensions."
                )
        if self.input_mode == "sheet" and self.extraction_mode == "grid":
            if self.cell_width is None or self.cell_height is None:
                raise ValueError(
                    "Grid sheet extraction requires cell_width and cell_height."
                )
            if (
                self.columns is not None
                and self.rows is not None
                and self.columns * self.rows > self.max_frames
            ):
                raise ValueError(
                    "Configured sheet grid exceeds the maximum frame count."
                )
        return self


class JobMetadata(BaseModel):
    job_id: str
    owner_id: str | None = None
    job_type: JobType = "restore"
    status: JobStatus
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    stage: str | None = None
    stage_message: str | None = None
    input_filename: str
    input_path: str
    input_filenames: list[str] = Field(default_factory=list)
    input_paths: list[str] = Field(default_factory=list)
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
    job_type: JobType = "restore"
    status: JobStatus
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    stage: str | None = None
    stage_message: str | None = None
    input_filename: str
    input_filenames: list[str] = Field(default_factory=list)
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


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0
