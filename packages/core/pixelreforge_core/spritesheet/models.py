from dataclasses import dataclass
from typing import Literal

from PIL import Image


PackingMode = Literal["compact", "grid"]
SpriteSortMode = Literal["input", "name", "width", "height", "area"]
SheetExtractionMode = Literal["auto", "grid"]
RgbaColor = tuple[int, int, int, int]


class SpriteSheetError(ValueError):
    """Raised when sprite-sheet input or settings are invalid."""


class AtlasSizeError(SpriteSheetError):
    """Raised when sprites cannot fit into the requested atlas bounds."""


@dataclass(frozen=True, slots=True)
class SpriteSheetSettings:
    """Controls deterministic sprite placement and atlas rendering."""

    packing_mode: PackingMode = "compact"
    trim_transparent: bool = True
    alpha_threshold: int = 0
    padding: int = 1
    border_padding: int = 0
    extrude: int = 0
    max_width: int = 2048
    max_height: int = 2048
    max_pixels: int = 16_000_000
    atlas_width: int | None = None
    atlas_height: int | None = None
    power_of_two: bool = False
    force_square: bool = False
    allow_rotation: bool = False
    sort_mode: SpriteSortMode = "area"
    grid_columns: int | None = None
    background_color: RgbaColor | None = None

    def __post_init__(self) -> None:
        if self.packing_mode not in ("compact", "grid"):
            raise SpriteSheetError("packing_mode must be 'compact' or 'grid'.")
        if self.sort_mode not in ("input", "name", "width", "height", "area"):
            raise SpriteSheetError("sort_mode is invalid.")
        if not 0 <= self.alpha_threshold <= 255:
            raise SpriteSheetError("alpha_threshold must be between 0 and 255.")
        for name, value in (
            ("padding", self.padding),
            ("border_padding", self.border_padding),
            ("extrude", self.extrude),
        ):
            if value < 0:
                raise SpriteSheetError(f"{name} must not be negative.")
        for name, value in (
            ("max_width", self.max_width),
            ("max_height", self.max_height),
        ):
            if value < 1:
                raise SpriteSheetError(f"{name} must be at least 1.")
        if self.max_pixels < 1:
            raise SpriteSheetError("max_pixels must be at least 1.")
        if (self.atlas_width is None) != (self.atlas_height is None):
            raise SpriteSheetError("atlas_width and atlas_height must be set together.")
        if self.atlas_width is not None and self.atlas_height is not None:
            if self.atlas_width < 1 or self.atlas_height < 1:
                raise SpriteSheetError("Fixed atlas dimensions must be positive.")
            if self.atlas_width > self.max_width or self.atlas_height > self.max_height:
                raise SpriteSheetError(
                    "Fixed atlas dimensions exceed the configured limits."
                )
        if self.grid_columns is not None and self.grid_columns < 1:
            raise SpriteSheetError("grid_columns must be at least 1.")
        if self.background_color is not None and any(
            channel < 0 or channel > 255 for channel in self.background_color
        ):
            raise SpriteSheetError(
                "background_color channels must be between 0 and 255."
            )


@dataclass(frozen=True, slots=True)
class SheetExtractionSettings:
    """Controls splitting an uploaded sheet into individual source sprites."""

    mode: SheetExtractionMode = "auto"
    cell_width: int | None = None
    cell_height: int | None = None
    columns: int | None = None
    rows: int | None = None
    offset_x: int = 0
    offset_y: int = 0
    gap_x: int = 0
    gap_y: int = 0
    alpha_threshold: int = 0
    max_frames: int = 4096

    def __post_init__(self) -> None:
        if self.mode not in ("auto", "grid"):
            raise SpriteSheetError("Sheet extraction mode must be 'auto' or 'grid'.")
        if not 0 <= self.alpha_threshold <= 255:
            raise SpriteSheetError("alpha_threshold must be between 0 and 255.")
        if self.max_frames < 1:
            raise SpriteSheetError("max_frames must be at least 1.")
        for name, value in (
            ("offset_x", self.offset_x),
            ("offset_y", self.offset_y),
            ("gap_x", self.gap_x),
            ("gap_y", self.gap_y),
        ):
            if value < 0:
                raise SpriteSheetError(f"{name} must not be negative.")
        for name, count in (("columns", self.columns), ("rows", self.rows)):
            if count is not None and count < 1:
                raise SpriteSheetError(f"{name} must be at least 1 when supplied.")
        if self.mode == "grid":
            if self.cell_width is None or self.cell_height is None:
                raise SpriteSheetError(
                    "Grid extraction requires cell_width and cell_height."
                )
            if self.cell_width < 1 or self.cell_height < 1:
                raise SpriteSheetError("Grid cell dimensions must be positive.")


@dataclass(frozen=True, slots=True)
class SpriteFrame:
    """A source sprite together with its untrimmed source geometry."""

    name: str
    image: Image.Image
    source_size: tuple[int, int]
    source_rect: tuple[int, int, int, int]
    trimmed: bool


@dataclass(frozen=True, slots=True)
class AtlasFrame:
    """A sprite's final placement and source geometry for metadata export."""

    name: str
    x: int
    y: int
    width: int
    height: int
    source_size: tuple[int, int]
    source_rect: tuple[int, int, int, int]
    trimmed: bool
    rotated: bool


@dataclass(frozen=True, slots=True)
class SpriteSheetResult:
    """The rendered atlas and portable JSON-compatible frame metadata."""

    atlas: Image.Image
    frames: tuple[AtlasFrame, ...]
    metadata: dict[str, object]
    warnings: tuple[str, ...] = ()
