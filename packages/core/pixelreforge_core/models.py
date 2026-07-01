from dataclasses import dataclass
from typing import Any, Literal

from PIL import Image


ScaleMode = Literal["auto", "manual"]
RestoreAlgorithm = Literal["auto", "integer-grid-v1", "resampled-grid-v2", "noisy-pixel-v1"]
PaletteCleanupMode = Literal["off", "light", "medium", "strong", "custom"]


@dataclass(frozen=True)
class RestoreSettings:
    algorithm: RestoreAlgorithm = "auto"
    scale_mode: ScaleMode = "auto"
    max_scale: int = 16
    min_scale: int = 2
    manual_scale_x: float | None = None
    manual_scale_y: float | None = None
    original_width: int | None = None
    original_height: int | None = None
    palette_cleanup: PaletteCleanupMode = "off"
    palette_merge_distance: float | None = None
    palette_target_colors: int | None = None
    noisy_color_bucket_size: int = 16
    confidence_threshold: float = 0.45
    fractional_scale_step: float = 0.25


@dataclass(frozen=True)
class ScaleEstimate:
    scale_x: float
    scale_y: float
    confidence_x: float
    confidence_y: float
    method: str

    @property
    def confidence(self) -> float:
        return min(self.confidence_x, self.confidence_y)


@dataclass(frozen=True)
class ProcessingResult:
    image: Image.Image
    scale: ScaleEstimate
    source_size: tuple[int, int]
    target_size: tuple[int, int]
    algorithm_requested: str = "integer-grid-v1"
    algorithm_used: str = "integer-grid-v1"
    algorithm_version: str = "integer-grid-v1"
    original_size_override: tuple[int, int] | None = None
    palette_cleanup: str = "off"
    analysis: dict[str, Any] | None = None
    palette: dict[str, Any] | None = None
    reconstruction: dict[str, Any] | None = None
    warnings: tuple[str, ...] = ()
