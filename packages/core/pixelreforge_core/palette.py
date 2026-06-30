from __future__ import annotations

from dataclasses import dataclass

from PIL import Image
import numpy as np


_MODE_DISTANCE = {
    "off": 0.0,
    "light": 10.0,
    "medium": 18.0,
    "strong": 30.0,
    "custom": 18.0,
}


@dataclass(frozen=True)
class PaletteResult:
    image: Image.Image
    metadata: dict[str, object]
    warnings: tuple[str, ...] = ()


def restore_palette(
    image: Image.Image,
    cleanup_mode: str,
    merge_distance: float | None = None,
    target_colors: int | None = None,
) -> PaletteResult:
    if cleanup_mode not in _MODE_DISTANCE:
        raise ValueError(f"Unsupported palette cleanup mode: {cleanup_mode}")

    image_array = np.asarray(image)
    analysis_array = _analysis_sample(image_array) if cleanup_mode == "off" else image_array
    before_colors, before_counts = _unique_colors(analysis_array)
    before_count = int(before_colors.shape[0])
    resolved_distance = _resolve_merge_distance(cleanup_mode, merge_distance)
    resolved_target_colors = target_colors if cleanup_mode == "custom" else None
    metadata: dict[str, object] = {
        "cleanup_requested": cleanup_mode,
        "cleanup_applied": False,
        "merge_distance": resolved_distance,
        "target_colors": resolved_target_colors,
        "color_count_before": before_count,
        "color_count_after": before_count,
        "top_colors_before": _top_colors(before_colors, before_counts),
        "top_colors_after": _top_colors(before_colors, before_counts),
    }

    if cleanup_mode == "off" or before_count <= 1:
        return PaletteResult(image=image, metadata=metadata)

    cleaned = _merge_similar_colors(image_array, before_colors, before_counts, resolved_distance)
    if resolved_target_colors is not None and resolved_target_colors > 0:
        cleaned = _limit_palette_colors(cleaned, resolved_target_colors)
    after_colors, after_counts = _unique_colors(cleaned)
    after_count = int(after_colors.shape[0])
    metadata.update(
        {
            "cleanup_applied": True,
            "color_count_after": after_count,
            "colors_merged": max(0, before_count - after_count),
            "top_colors_after": _top_colors(after_colors, after_counts),
        }
    )

    mode = "RGBA" if cleaned.shape[2] == 4 else "RGB"
    return PaletteResult(image=Image.fromarray(cleaned, mode=mode), metadata=metadata)


def _resolve_merge_distance(cleanup_mode: str, merge_distance: float | None) -> float:
    if cleanup_mode == "custom" and merge_distance is not None:
        return max(0.0, float(merge_distance))
    return _MODE_DISTANCE[cleanup_mode]


def _analysis_sample(image_array: np.ndarray, max_pixels: int = 65_536) -> np.ndarray:
    pixel_count = image_array.shape[0] * image_array.shape[1]
    if pixel_count <= max_pixels:
        return image_array
    step = max(1, int((pixel_count / max_pixels) ** 0.5))
    return image_array[::step, ::step]


def _merge_similar_colors(
    image_array: np.ndarray,
    colors: np.ndarray,
    counts: np.ndarray,
    distance: float,
) -> np.ndarray:
    order = np.argsort(-counts)
    representatives: list[np.ndarray] = []
    mapping: dict[tuple[int, ...], np.ndarray] = {}

    for color_index in order:
        color = colors[int(color_index)]
        representative = _nearest_representative(color, representatives, distance)
        if representative is None:
            representative = color
            representatives.append(representative)
        mapping[tuple(int(value) for value in color)] = representative

    flat = image_array.reshape(-1, image_array.shape[2])
    cleaned = np.empty_like(flat)
    for index, pixel in enumerate(flat):
        cleaned[index] = mapping[tuple(int(value) for value in pixel)]
    return cleaned.reshape(image_array.shape)


def _nearest_representative(color: np.ndarray, representatives: list[np.ndarray], max_distance: float) -> np.ndarray | None:
    best: np.ndarray | None = None
    best_distance = max_distance
    for representative in representatives:
        current_distance = _color_distance(color, representative)
        if current_distance <= best_distance:
            best = representative
            best_distance = current_distance
    return best


def _limit_palette_colors(image_array: np.ndarray, target_colors: int) -> np.ndarray:
    colors, counts = _unique_colors(image_array)
    if colors.shape[0] <= target_colors:
        return image_array

    keep_indexes = np.argsort(-counts)[:target_colors]
    palette = colors[keep_indexes]
    flat = image_array.reshape(-1, image_array.shape[2])
    limited = np.empty_like(flat)
    for index, pixel in enumerate(flat):
        distances = np.array([_color_distance(pixel, color) for color in palette], dtype=np.float64)
        limited[index] = palette[int(np.argmin(distances))]
    return limited.reshape(image_array.shape)


def _color_distance(left: np.ndarray, right: np.ndarray) -> float:
    rgb_distance = float(np.linalg.norm(left[:3].astype(np.int16) - right[:3].astype(np.int16)))
    if left.shape[0] == 4:
        alpha_distance = abs(int(left[3]) - int(right[3])) * 2.0
        return rgb_distance + alpha_distance
    return rgb_distance


def _unique_colors(image_array: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    pixels = image_array.reshape(-1, image_array.shape[2])
    colors, counts = np.unique(pixels, axis=0, return_counts=True)
    return colors.astype(np.uint8, copy=False), counts.astype(np.int64, copy=False)


def _top_colors(colors: np.ndarray, counts: np.ndarray, limit: int = 16) -> list[dict[str, object]]:
    total = max(1, int(counts.sum()))
    top_indexes = np.argsort(-counts)[:limit]
    return [
        {
            "color": _hex_color(colors[int(index)]),
            "count": int(counts[int(index)]),
            "percentage": round(float(counts[int(index)] / total), 6),
        }
        for index in top_indexes
    ]


def _hex_color(color: np.ndarray) -> str:
    if color.shape[0] == 4:
        return "#{:02x}{:02x}{:02x}{:02x}".format(int(color[0]), int(color[1]), int(color[2]), int(color[3]))
    return "#{:02x}{:02x}{:02x}".format(int(color[0]), int(color[1]), int(color[2]))
