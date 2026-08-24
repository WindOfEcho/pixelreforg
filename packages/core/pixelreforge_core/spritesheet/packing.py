from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import ceil, sqrt

from PIL import Image

from ..models import CancelCallback, ProcessingCancelled
from .models import (
    AtlasFrame,
    AtlasSizeError,
    SpriteFrame,
    SpriteSheetError,
    SpriteSheetSettings,
)


@dataclass(frozen=True, slots=True)
class _Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True, slots=True)
class _Placement:
    frame_index: int
    x: int
    y: int
    content_width: int
    content_height: int
    rotated: bool


@dataclass(frozen=True, slots=True)
class PackedAtlas:
    atlas: Image.Image
    frames: tuple[AtlasFrame, ...]


def pack_frames(
    frames: Sequence[SpriteFrame],
    settings: SpriteSheetSettings,
    *,
    cancel: CancelCallback | None = None,
) -> PackedAtlas:
    """Lay out source frames in a regular grid or compact MaxRects atlas."""

    if not frames:
        raise SpriteSheetError("At least one sprite frame is required.")
    ordered_indices = _ordered_indices(frames, settings.sort_mode)
    if settings.packing_mode == "grid":
        placements, output_size = _pack_grid(frames, ordered_indices, settings)
    else:
        placements, output_size = _pack_compact(
            frames, ordered_indices, settings, cancel
        )
    return _render(frames, placements, output_size, settings)


def _pack_grid(
    frames: Sequence[SpriteFrame],
    ordered_indices: Sequence[int],
    settings: SpriteSheetSettings,
) -> tuple[list[_Placement], tuple[int, int]]:
    if settings.atlas_width is not None and settings.atlas_height is not None:
        _resolve_output_size(settings.atlas_width, settings.atlas_height, settings)
    extrude = settings.extrude
    cell_width = max(frame.image.width + 2 * extrude for frame in frames)
    cell_height = max(frame.image.height + 2 * extrude for frame in frames)
    count = len(frames)
    columns = settings.grid_columns or _best_grid_columns(
        count, cell_width, cell_height, settings
    )
    rows = ceil(count / columns)
    required_width = _grid_extent(
        columns, cell_width, settings.padding, settings.border_padding
    )
    required_height = _grid_extent(
        rows, cell_height, settings.padding, settings.border_padding
    )
    output_size = _resolve_output_size(required_width, required_height, settings)
    if required_width > output_size[0] or required_height > output_size[1]:
        raise AtlasSizeError(
            "Sprites do not fit in the requested grid atlas dimensions."
        )

    placements: list[_Placement] = []
    for placement_index, frame_index in enumerate(ordered_indices):
        row, column = divmod(placement_index, columns)
        frame = frames[frame_index]
        placements.append(
            _Placement(
                frame_index=frame_index,
                x=settings.border_padding + column * (cell_width + settings.padding),
                y=settings.border_padding + row * (cell_height + settings.padding),
                content_width=frame.image.width + 2 * extrude,
                content_height=frame.image.height + 2 * extrude,
                rotated=False,
            )
        )
    return placements, output_size


def _best_grid_columns(
    count: int, cell_width: int, cell_height: int, settings: SpriteSheetSettings
) -> int:
    candidates: list[tuple[int, int]] = []
    for columns in range(1, count + 1):
        rows = ceil(count / columns)
        width = _grid_extent(
            columns, cell_width, settings.padding, settings.border_padding
        )
        height = _grid_extent(
            rows, cell_height, settings.padding, settings.border_padding
        )
        try:
            output_width, output_height = _resolve_output_size(width, height, settings)
        except AtlasSizeError:
            continue
        candidates.append((output_width * output_height, columns))
    if not candidates:
        raise AtlasSizeError("Sprites do not fit within the configured atlas limits.")
    return min(candidates)[1]


def _grid_extent(count: int, cell_size: int, padding: int, border: int) -> int:
    return 2 * border + count * cell_size + max(0, count - 1) * padding


def _pack_compact(
    frames: Sequence[SpriteFrame],
    ordered_indices: Sequence[int],
    settings: SpriteSheetSettings,
    cancel: CancelCallback | None,
) -> tuple[list[_Placement], tuple[int, int]]:
    if settings.atlas_width is not None and settings.atlas_height is not None:
        _resolve_output_size(settings.atlas_width, settings.atlas_height, settings)
    content_sizes = [
        _minimum_content_size(frames[index], settings) for index in ordered_indices
    ]
    outer_sizes = [
        _outer_size(frames[index], settings, False) for index in ordered_indices
    ]
    minimum_width = max(width for width, _ in content_sizes)
    minimum_height = max(height for _, height in content_sizes)
    total_area = sum(width * height for width, height in outer_sizes)
    candidates = _compact_candidates(
        minimum_width, minimum_height, total_area, settings
    )
    best: tuple[tuple[int, int, int], list[_Placement], tuple[int, int]] | None = None

    for inner_width, inner_height in candidates:
        _check_cancel(cancel)
        # The virtual trailing gutter lets the final row and column end at the
        # atlas edge while preserving padding between every pair of frames.
        placements = _maxrects_pack(
            frames,
            ordered_indices,
            inner_width + settings.padding,
            inner_height + settings.padding,
            settings,
            content_width_limit=inner_width,
            content_height_limit=inner_height,
        )
        if placements is None:
            continue
        used_width = (
            max(placement.x + placement.content_width for placement in placements)
            + settings.border_padding
        )
        used_height = (
            max(placement.y + placement.content_height for placement in placements)
            + settings.border_padding
        )
        output_size = _resolve_output_size(used_width, used_height, settings)
        if (
            output_size[0] > inner_width + 2 * settings.border_padding
            or output_size[1] > inner_height + 2 * settings.border_padding
        ):
            continue
        score = (output_size[0] * output_size[1], max(output_size), min(output_size))
        if best is None or score < best[0]:
            best = (score, placements, output_size)

    if best is None:
        raise AtlasSizeError(
            "Sprites do not fit within the configured atlas dimensions."
        )
    return best[1], best[2]


def _compact_candidates(
    minimum_width: int,
    minimum_height: int,
    total_area: int,
    settings: SpriteSheetSettings,
) -> list[tuple[int, int]]:
    border = settings.border_padding
    if settings.atlas_width is not None and settings.atlas_height is not None:
        return [(settings.atlas_width - 2 * border, settings.atlas_height - 2 * border)]

    max_inner_width = settings.max_width - 2 * border
    max_inner_height = settings.max_height - 2 * border
    if minimum_width > max_inner_width or minimum_height > max_inner_height:
        raise AtlasSizeError("A sprite is larger than the configured atlas limits.")

    if settings.power_of_two:
        widths = [
            value - 2 * border
            for value in _power_of_two_values(
                minimum_width + 2 * border, settings.max_width
            )
        ]
        heights = [
            value - 2 * border
            for value in _power_of_two_values(
                minimum_height + 2 * border, settings.max_height
            )
        ]
    else:
        preferred_width = max(minimum_width, ceil(sqrt(total_area)))
        preferred_height = max(minimum_height, ceil(total_area / preferred_width))
        widths = _dimension_candidates(minimum_width, max_inner_width, preferred_width)
        heights = _dimension_candidates(
            minimum_height, max_inner_height, preferred_height
        )

    if settings.force_square:
        sides = sorted(set(widths) | set(heights))
        return [
            (side, side)
            for side in sides
            if side <= max_inner_width
            and side <= max_inner_height
            and (side + 2 * border) ** 2 <= settings.max_pixels
        ]
    return sorted(
        (
            (width, height)
            for width in widths
            for height in heights
            if (width + 2 * border) * (height + 2 * border) <= settings.max_pixels
        ),
        key=lambda value: (value[0] * value[1], max(value), min(value)),
    )


def _power_of_two_values(minimum: int, maximum: int) -> list[int]:
    value = _next_power_of_two(minimum)
    values: list[int] = []
    while value <= maximum:
        values.append(value)
        value *= 2
    return values


def _dimension_candidates(minimum: int, maximum: int, preferred: int) -> list[int]:
    if minimum == maximum:
        return [minimum]
    values = {minimum, maximum, min(maximum, max(minimum, preferred))}
    for step in range(1, 7):
        values.add(minimum + (maximum - minimum) * step // 7)
    if maximum > minimum:
        values.add(maximum - 1)
    return sorted(values)


def _maxrects_pack(
    frames: Sequence[SpriteFrame],
    ordered_indices: Sequence[int],
    width: int,
    height: int,
    settings: SpriteSheetSettings,
    *,
    content_width_limit: int,
    content_height_limit: int,
) -> list[_Placement] | None:
    if width < 1 or height < 1:
        return None
    free_rectangles = [
        _Rect(settings.border_padding, settings.border_padding, width, height)
    ]
    placements: list[_Placement] = []
    for frame_index in ordered_indices:
        frame = frames[frame_index]
        candidate = _best_placement(
            frame,
            free_rectangles,
            settings,
            content_right_limit=settings.border_padding + content_width_limit,
            content_bottom_limit=settings.border_padding + content_height_limit,
        )
        if candidate is None:
            return None
        placement, occupied = candidate
        placements.append(
            _Placement(
                frame_index=frame_index,
                x=placement.x,
                y=placement.y,
                content_width=placement.content_width,
                content_height=placement.content_height,
                rotated=placement.rotated,
            )
        )
        free_rectangles = _split_free_rectangles(free_rectangles, occupied)
    return placements


def _best_placement(
    frame: SpriteFrame,
    free_rectangles: Sequence[_Rect],
    settings: SpriteSheetSettings,
    *,
    content_right_limit: int,
    content_bottom_limit: int,
) -> tuple[_Placement, _Rect] | None:
    best: tuple[tuple[int, int, int, int, int], _Placement, _Rect] | None = None
    orientations = [False]
    if settings.allow_rotation and frame.image.width != frame.image.height:
        orientations.append(True)
    for rotated in orientations:
        content_width, content_height = _content_size(frame, settings.extrude, rotated)
        occupied_width = content_width + settings.padding
        occupied_height = content_height + settings.padding
        for rect in free_rectangles:
            if occupied_width > rect.width or occupied_height > rect.height:
                continue
            if (
                rect.x + content_width > content_right_limit
                or rect.y + content_height > content_bottom_limit
            ):
                continue
            horizontal = rect.width - occupied_width
            vertical = rect.height - occupied_height
            score = (
                min(horizontal, vertical),
                max(horizontal, vertical),
                rect.y,
                rect.x,
                int(rotated),
            )
            placement = _Placement(
                frame_index=-1,
                x=rect.x,
                y=rect.y,
                content_width=content_width,
                content_height=content_height,
                rotated=rotated,
            )
            occupied = _Rect(rect.x, rect.y, occupied_width, occupied_height)
            if best is None or score < best[0]:
                best = (score, placement, occupied)
    if best is None:
        return None
    _, placement, occupied = best
    return placement, occupied


def _split_free_rectangles(
    free_rectangles: Sequence[_Rect], occupied: _Rect
) -> list[_Rect]:
    split: list[_Rect] = []
    for free in free_rectangles:
        if not _intersects(free, occupied):
            split.append(free)
            continue
        if occupied.x > free.x:
            split.append(_Rect(free.x, free.y, occupied.x - free.x, free.height))
        if occupied.right < free.right:
            split.append(
                _Rect(occupied.right, free.y, free.right - occupied.right, free.height)
            )
        if occupied.y > free.y:
            split.append(_Rect(free.x, free.y, free.width, occupied.y - free.y))
        if occupied.bottom < free.bottom:
            split.append(
                _Rect(
                    free.x, occupied.bottom, free.width, free.bottom - occupied.bottom
                )
            )
    return _prune_contained_rectangles(split)


def _intersects(left: _Rect, right: _Rect) -> bool:
    return (
        left.x < right.right
        and left.right > right.x
        and left.y < right.bottom
        and left.bottom > right.y
    )


def _prune_contained_rectangles(rectangles: Sequence[_Rect]) -> list[_Rect]:
    result: list[_Rect] = []
    for index, candidate in enumerate(rectangles):
        if candidate.width < 1 or candidate.height < 1:
            continue
        if any(
            other_index != index
            and _contains(other, candidate)
            and (other != candidate or other_index < index)
            for other_index, other in enumerate(rectangles)
        ):
            continue
        result.append(candidate)
    return result


def _contains(outer: _Rect, inner: _Rect) -> bool:
    return (
        outer.x <= inner.x
        and outer.y <= inner.y
        and outer.right >= inner.right
        and outer.bottom >= inner.bottom
    )


def _outer_size(
    frame: SpriteFrame, settings: SpriteSheetSettings, rotated: bool
) -> tuple[int, int]:
    width, height = _content_size(frame, settings.extrude, rotated)
    return width + settings.padding, height + settings.padding


def _content_size(frame: SpriteFrame, extrude: int, rotated: bool) -> tuple[int, int]:
    width = frame.image.width + 2 * extrude
    height = frame.image.height + 2 * extrude
    return (height, width) if rotated else (width, height)


def _minimum_content_size(
    frame: SpriteFrame, settings: SpriteSheetSettings
) -> tuple[int, int]:
    width, height = _content_size(frame, settings.extrude, False)
    if not settings.allow_rotation:
        return width, height
    shortest_side = min(width, height)
    return shortest_side, shortest_side


def _resolve_output_size(
    required_width: int, required_height: int, settings: SpriteSheetSettings
) -> tuple[int, int]:
    if settings.atlas_width is not None and settings.atlas_height is not None:
        width, height = settings.atlas_width, settings.atlas_height
    else:
        width, height = required_width, required_height
        if settings.power_of_two:
            width = _next_power_of_two(width)
            height = _next_power_of_two(height)
        if settings.force_square:
            side = max(width, height)
            width = height = side
    if width > settings.max_width or height > settings.max_height:
        raise AtlasSizeError("Required atlas dimensions exceed the configured limits.")
    if width * height > settings.max_pixels:
        raise AtlasSizeError("Required atlas pixel count exceeds the configured limit.")
    if required_width > width or required_height > height:
        raise AtlasSizeError("Sprites do not fit in the requested atlas dimensions.")
    if settings.power_of_two and (
        not _is_power_of_two(width) or not _is_power_of_two(height)
    ):
        raise AtlasSizeError(
            "Power-of-two output requires power-of-two atlas dimensions."
        )
    if settings.force_square and width != height:
        raise AtlasSizeError("Square output requires equal atlas dimensions.")
    return width, height


def _next_power_of_two(value: int) -> int:
    return 1 if value <= 1 else 1 << (value - 1).bit_length()


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def _render(
    frames: Sequence[SpriteFrame],
    placements: Sequence[_Placement],
    output_size: tuple[int, int],
    settings: SpriteSheetSettings,
) -> PackedAtlas:
    atlas = Image.new("RGBA", output_size, settings.background_color or (0, 0, 0, 0))
    placements_by_frame = {placement.frame_index: placement for placement in placements}
    metadata_frames: list[AtlasFrame] = []
    for frame_index, frame in enumerate(frames):
        placement = placements_by_frame[frame_index]
        expanded = _extruded_image(frame.image, settings.extrude)
        if placement.rotated:
            expanded = expanded.transpose(Image.Transpose.ROTATE_90)
        atlas.alpha_composite(expanded, (placement.x, placement.y))
        metadata_frames.append(
            AtlasFrame(
                name=frame.name,
                x=placement.x + settings.extrude,
                y=placement.y + settings.extrude,
                width=placement.content_width - 2 * settings.extrude,
                height=placement.content_height - 2 * settings.extrude,
                source_size=frame.source_size,
                source_rect=frame.source_rect,
                trimmed=frame.trimmed,
                rotated=placement.rotated,
            )
        )
    return PackedAtlas(atlas=atlas, frames=tuple(metadata_frames))


def _extruded_image(image: Image.Image, amount: int) -> Image.Image:
    if amount == 0:
        return image
    width, height = image.size
    expanded = Image.new(
        "RGBA", (width + 2 * amount, height + 2 * amount), (0, 0, 0, 0)
    )
    expanded.alpha_composite(image, (amount, amount))
    nearest = Image.Resampling.NEAREST
    expanded.alpha_composite(
        image.crop((0, 0, width, 1)).resize((width, amount), nearest), (amount, 0)
    )
    expanded.alpha_composite(
        image.crop((0, height - 1, width, height)).resize((width, amount), nearest),
        (amount, amount + height),
    )
    expanded.alpha_composite(
        image.crop((0, 0, 1, height)).resize((amount, height), nearest), (0, amount)
    )
    expanded.alpha_composite(
        image.crop((width - 1, 0, width, height)).resize((amount, height), nearest),
        (amount + width, amount),
    )
    expanded.alpha_composite(
        image.crop((0, 0, 1, 1)).resize((amount, amount), nearest), (0, 0)
    )
    expanded.alpha_composite(
        image.crop((width - 1, 0, width, 1)).resize((amount, amount), nearest),
        (amount + width, 0),
    )
    expanded.alpha_composite(
        image.crop((0, height - 1, 1, height)).resize((amount, amount), nearest),
        (0, amount + height),
    )
    expanded.alpha_composite(
        image.crop((width - 1, height - 1, width, height)).resize(
            (amount, amount), nearest
        ),
        (amount + width, amount + height),
    )
    return expanded


def _ordered_indices(frames: Sequence[SpriteFrame], sort_mode: str) -> list[int]:
    indices = list(range(len(frames)))
    if sort_mode == "input":
        return indices
    if sort_mode == "name":
        return sorted(indices, key=lambda index: frames[index].name.casefold())
    if sort_mode == "width":
        return sorted(
            indices,
            key=lambda index: (
                -frames[index].image.width,
                -frames[index].image.height,
                frames[index].name.casefold(),
            ),
        )
    if sort_mode == "height":
        return sorted(
            indices,
            key=lambda index: (
                -frames[index].image.height,
                -frames[index].image.width,
                frames[index].name.casefold(),
            ),
        )
    return sorted(
        indices,
        key=lambda index: (
            -frames[index].image.width * frames[index].image.height,
            -frames[index].image.height,
            -frames[index].image.width,
            frames[index].name.casefold(),
        ),
    )


def _check_cancel(cancel: Callable[[], bool] | None) -> None:
    if cancel is not None and cancel():
        raise ProcessingCancelled("Sprite-sheet processing was cancelled.")
