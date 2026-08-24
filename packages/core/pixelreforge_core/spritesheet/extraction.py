from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
from PIL import Image

from ..models import CancelCallback, ProcessingCancelled
from .models import SheetExtractionSettings, SpriteFrame, SpriteSheetError, SpriteSheetSettings


def extract_sprites_from_sheet(
    image: Image.Image,
    settings: SheetExtractionSettings,
    *,
    name_prefix: str = "frame",
    cancel: CancelCallback | None = None,
) -> list[SpriteFrame]:
    """Split a sheet by connected alpha regions or by a user-defined grid."""

    rgba = image.convert("RGBA")
    if settings.mode == "grid":
        frames = _extract_grid(rgba, settings, name_prefix, cancel)
    else:
        frames = _extract_connected_regions(rgba, settings, name_prefix, cancel)
    if not frames:
        raise SpriteSheetError("No non-transparent sprites were found in the uploaded sheet.")
    return frames


def frames_from_images(
    images: Sequence[Image.Image],
    names: Sequence[str],
    settings: SpriteSheetSettings,
    *,
    cancel: CancelCallback | None = None,
) -> tuple[list[SpriteFrame], tuple[str, ...]]:
    """Normalize, name, and optionally trim independently uploaded sprites."""

    if not images:
        raise SpriteSheetError("At least one sprite image is required.")
    if len(images) != len(names):
        raise SpriteSheetError("Each sprite image requires a matching name.")

    frames: list[SpriteFrame] = []
    warnings: list[str] = []
    unique_names = _unique_names(names)
    for index, (image, name) in enumerate(zip(images, unique_names, strict=True)):
        _check_cancel(cancel)
        rgba = image.convert("RGBA")
        frame, was_empty = _trim_frame(rgba, name, settings.trim_transparent, settings.alpha_threshold, cancel)
        frames.append(frame)
        _check_cancel(cancel)
        if was_empty:
            warnings.append(f"Sprite '{name}' is fully transparent and was kept as a 1 x 1 frame.")
    return frames, tuple(warnings)


def _extract_connected_regions(
    image: Image.Image,
    settings: SheetExtractionSettings,
    name_prefix: str,
    cancel: CancelCallback | None,
) -> list[SpriteFrame]:
    alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
    mask = alpha > settings.alpha_threshold
    bounds = _connected_bounds(mask, cancel, settings.max_frames)
    frames: list[SpriteFrame] = []
    for index, (left, top, right, bottom) in enumerate(bounds, start=1):
        _check_cancel(cancel)
        sprite = image.crop((left, top, right, bottom))
        frames.append(
            SpriteFrame(
                name=f"{name_prefix}_{index:04d}",
                image=sprite,
                source_size=sprite.size,
                source_rect=(0, 0, sprite.width, sprite.height),
                trimmed=False,
            )
        )
    return frames


def _extract_grid(
    image: Image.Image,
    settings: SheetExtractionSettings,
    name_prefix: str,
    cancel: CancelCallback | None,
) -> list[SpriteFrame]:
    assert settings.cell_width is not None
    assert settings.cell_height is not None
    available_columns = _available_cells(image.width, settings.offset_x, settings.cell_width, settings.gap_x)
    available_rows = _available_cells(image.height, settings.offset_y, settings.cell_height, settings.gap_y)
    columns = settings.columns or available_columns
    rows = settings.rows or available_rows
    if columns > available_columns or rows > available_rows:
        raise SpriteSheetError("The configured grid extends outside the uploaded sheet.")
    if columns * rows > settings.max_frames:
        raise SpriteSheetError("Sheet extraction exceeds the maximum frame count.")

    alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
    frames: list[SpriteFrame] = []
    frame_number = 1
    for row in range(rows):
        for column in range(columns):
            _check_cancel(cancel)
            left = settings.offset_x + column * (settings.cell_width + settings.gap_x)
            top = settings.offset_y + row * (settings.cell_height + settings.gap_y)
            right = left + settings.cell_width
            bottom = top + settings.cell_height
            if not np.any(alpha[top:bottom, left:right] > settings.alpha_threshold):
                continue
            sprite = image.crop((left, top, right, bottom))
            frames.append(
                SpriteFrame(
                    name=f"{name_prefix}_{frame_number:04d}",
                    image=sprite,
                    source_size=sprite.size,
                    source_rect=(0, 0, sprite.width, sprite.height),
                    trimmed=False,
                )
            )
            frame_number += 1
    return frames


def _available_cells(length: int, offset: int, cell_size: int, gap: int) -> int:
    if offset >= length:
        return 0
    return (length - offset + gap) // (cell_size + gap)


def _connected_bounds(
    mask: np.ndarray,
    cancel: CancelCallback | None,
    max_frames: int,
) -> list[tuple[int, int, int, int]]:
    height, width = mask.shape
    visited = np.zeros(mask.shape, dtype=bool)
    bounds: list[tuple[int, int, int, int]] = []

    for top in range(height):
        if top % 32 == 0:
            _check_cancel(cancel)
        for left in range(width):
            if not mask[top, left] or visited[top, left]:
                continue
            visited[top, left] = True
            stack = [(left, top)]
            min_x = max_x = left
            min_y = max_y = top
            processed_pixels = 0
            while stack:
                processed_pixels += 1
                if processed_pixels % 4096 == 0:
                    _check_cancel(cancel)
                x, y = stack.pop()
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
                for next_y in range(max(0, y - 1), min(height, y + 2)):
                    for next_x in range(max(0, x - 1), min(width, x + 2)):
                        if mask[next_y, next_x] and not visited[next_y, next_x]:
                            visited[next_y, next_x] = True
                            stack.append((next_x, next_y))
            bounds.append((min_x, min_y, max_x + 1, max_y + 1))
            if len(bounds) > max_frames:
                raise SpriteSheetError("Sheet extraction exceeds the maximum frame count.")
    return sorted(bounds, key=lambda value: (value[1], value[0]))


def _trim_frame(
    image: Image.Image,
    name: str,
    trim: bool,
    alpha_threshold: int,
    cancel: CancelCallback | None,
) -> tuple[SpriteFrame, bool]:
    source_width, source_height = image.size
    if not trim:
        return SpriteFrame(name, image, image.size, (0, 0, source_width, source_height), False), False

    _check_cancel(cancel)
    alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
    opaque = alpha > alpha_threshold
    occupied_rows = np.flatnonzero(np.any(opaque, axis=1))
    occupied_columns = np.flatnonzero(np.any(opaque, axis=0))
    _check_cancel(cancel)
    if occupied_rows.size == 0 or occupied_columns.size == 0:
        empty = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        return SpriteFrame(name, empty, image.size, (0, 0, 1, 1), True), True
    top = int(occupied_rows[0])
    bottom = int(occupied_rows[-1]) + 1
    left = int(occupied_columns[0])
    right = int(occupied_columns[-1]) + 1
    source_rect = (int(left), int(top), int(right - left), int(bottom - top))
    trimmed = source_rect != (0, 0, source_width, source_height)
    return SpriteFrame(name, image.crop((left, top, right, bottom)), image.size, source_rect, trimmed), False


def _unique_names(names: Sequence[str]) -> list[str]:
    used: dict[str, int] = {}
    result: list[str] = []
    for index, name in enumerate(names, start=1):
        base = Path(name).stem.strip() or f"sprite_{index:04d}"
        count = used.get(base, 0) + 1
        used[base] = count
        result.append(base if count == 1 else f"{base}_{count}")
    return result


def _check_cancel(cancel: Callable[[], bool] | None) -> None:
    if cancel is not None and cancel():
        raise ProcessingCancelled("Sprite-sheet processing was cancelled.")
