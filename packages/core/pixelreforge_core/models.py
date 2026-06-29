from dataclasses import dataclass
from typing import Literal

from PIL import Image


ScaleMode = Literal["auto", "manual"]


@dataclass(frozen=True)
class RestoreSettings:
    scale_mode: ScaleMode = "auto"
    max_scale: int = 16
    min_scale: int = 2
    manual_scale_x: int | None = None
    manual_scale_y: int | None = None
    confidence_threshold: float = 0.45


@dataclass(frozen=True)
class ScaleEstimate:
    scale_x: int
    scale_y: int
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
    warnings: tuple[str, ...] = ()
