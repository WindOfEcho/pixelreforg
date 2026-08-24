from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, sqrt

import numpy as np
from PIL import Image

from .models import RestoreSettings, ScaleEstimate


COMMON_SCALES = (2.0, 3.0, 3.5, 3.6, 4.0, 4.5, 5.0, 6.0, 6.3, 8.0, 10.0, 12.0, 16.0)
COMMON_TARGET_SIZES = (16, 24, 32, 40, 48, 64, 80, 96, 128, 160, 192, 256)


@dataclass(frozen=True)
class GridHypothesis:
    target_width: int
    target_height: int
    scale_x: float
    scale_y: float
    score: float
    components: dict[str, float]


def detect_ai_grid_hypothesis_scale(
    image_array: np.ndarray, settings: RestoreSettings
) -> ScaleEstimate:
    height, width = image_array.shape[:2]
    candidates = _candidate_target_sizes(
        width, height, settings.min_scale, settings.max_scale
    )
    if not candidates:
        return ScaleEstimate(
            1.0,
            1.0,
            0.0,
            0.0,
            "ai-grid-hypothesis-v1",
            {"candidate_count": 0, "top_candidates": []},
        )

    horizontal_signal = _boundary_signal(image_array, axis="x")
    vertical_signal = _boundary_signal(image_array, axis="y")
    image = _to_pil(image_array)
    scored = [
        _score_hypothesis(
            image,
            image_array,
            target_width,
            target_height,
            horizontal_signal,
            vertical_signal,
        )
        for target_width, target_height in candidates
    ]
    scored.sort(key=lambda item: item.score, reverse=True)

    best = scored[0]
    second_score = scored[1].score if len(scored) > 1 else 0.0
    confidence = _clamp01(
        (best.score * 0.72) + min(0.28, max(0.0, best.score - second_score) * 2.5)
    )
    details = {
        "candidate_count": len(scored),
        "top_candidates": [_hypothesis_metadata(candidate) for candidate in scored[:5]],
    }
    return ScaleEstimate(
        best.scale_x,
        best.scale_y,
        confidence,
        confidence,
        "ai-grid-hypothesis-v1",
        details,
    )


def _candidate_target_sizes(
    width: int, height: int, min_scale: int, max_scale: int
) -> list[tuple[int, int]]:
    min_scale = max(1, int(min_scale))
    max_scale = max(min_scale, int(max_scale))
    candidates: set[tuple[int, int]] = set()

    for scale in COMMON_SCALES:
        if min_scale <= scale <= max_scale:
            candidates.add(
                (max(1, int(round(width / scale))), max(1, int(round(height / scale))))
            )

    aspect = height / max(1, width)
    for target_width in COMMON_TARGET_SIZES:
        target_height = max(1, int(round(target_width * aspect)))
        candidates.add((target_width, target_height))

    return sorted(
        (target_width, target_height)
        for target_width, target_height in candidates
        if _target_size_is_valid(
            width, height, target_width, target_height, min_scale, max_scale
        )
    )


def _target_size_is_valid(
    width: int,
    height: int,
    target_width: int,
    target_height: int,
    min_scale: int,
    max_scale: int,
) -> bool:
    if target_width < 4 or target_height < 4:
        return False
    if target_width >= width or target_height >= height:
        return False
    scale_x = width / target_width
    scale_y = height / target_height
    return min_scale <= scale_x <= max_scale and min_scale <= scale_y <= max_scale


def _score_hypothesis(
    image: Image.Image,
    image_array: np.ndarray,
    target_width: int,
    target_height: int,
    horizontal_signal: np.ndarray,
    vertical_signal: np.ndarray,
) -> GridHypothesis:
    height, width = image_array.shape[:2]
    restored = image.resize((target_width, target_height), Image.Resampling.BOX)
    reconstructed = restored.resize((width, height), Image.Resampling.NEAREST)

    source_rgb = image_array[:, :, :3].astype(np.float32, copy=False)
    reconstructed_rgb = np.asarray(reconstructed)[:, :, :3].astype(
        np.float32, copy=False
    )
    normalized_mae = float(np.mean(np.abs(source_rgb - reconstructed_rgb)) / 255.0)
    reconstruction_score = 1.0 - min(1.0, normalized_mae / 0.35)

    restored_array = np.asarray(restored)
    palette_score = _palette_compactness_score(restored_array)
    grid_score_x = _target_size_confidence(horizontal_signal, width, target_width)
    grid_score_y = _target_size_confidence(vertical_signal, height, target_height)
    grid_score = (grid_score_x + grid_score_y) / 2.0
    scale_x = width / target_width
    scale_y = height / target_height
    scale_prior = _scale_prior_score(sqrt(scale_x * scale_y))
    xy_consistency = 1.0 - min(1.0, abs(log(scale_x / scale_y)) / log(2.0))

    score = (
        (reconstruction_score * 0.30)
        + (palette_score * 0.25)
        + (grid_score * 0.20)
        + (scale_prior * 0.20)
        + (xy_consistency * 0.05)
    )
    components = {
        "reconstruction": reconstruction_score,
        "palette_compactness": palette_score,
        "edge_grid_alignment": grid_score,
        "scale_prior": scale_prior,
        "xy_consistency": xy_consistency,
        "normalized_mae": normalized_mae,
    }
    return GridHypothesis(
        target_width, target_height, scale_x, scale_y, _clamp01(score), components
    )


def _palette_compactness_score(image_array: np.ndarray) -> float:
    pixels = image_array.reshape(-1, image_array.shape[2])
    quantized = (pixels[:, :3] // 16).astype(np.uint8, copy=False)
    if pixels.shape[1] == 4:
        alpha = (pixels[:, 3:4] // 32).astype(np.uint8, copy=False)
        quantized = np.concatenate((quantized, alpha), axis=1)
    estimated_palette_size = int(np.unique(quantized, axis=0).shape[0])
    return 1.0 - min(1.0, max(0, estimated_palette_size - 16) / 240.0)


def _scale_prior_score(scale: float) -> float:
    if scale <= 1.0:
        return 0.0
    distance = log(scale / 6.0)
    return _clamp01(exp(-((distance * distance) / (2.0 * (log(2.0) ** 2)))))


def _boundary_signal(image_array: np.ndarray, axis: str) -> np.ndarray:
    data = image_array.astype(np.int16, copy=False)
    if axis == "x":
        diff = np.abs(data[:, 1:, :3] - data[:, :-1, :3]).sum(axis=2)
        return diff.sum(axis=0).astype(np.float64)
    if axis == "y":
        diff = np.abs(data[1:, :, :3] - data[:-1, :, :3]).sum(axis=2)
        return diff.sum(axis=1).astype(np.float64)
    raise ValueError(f"Unsupported axis: {axis}")


def _target_size_confidence(
    signal: np.ndarray, image_size: int, target_size: int
) -> float:
    if target_size <= 1 or target_size >= image_size:
        return 0.0
    boundaries = (
        np.rint(np.arange(1, target_size) * image_size / target_size).astype(np.int64)
        - 1
    )
    boundaries = boundaries[(boundaries >= 0) & (boundaries < signal.size)]
    if boundaries.size == 0:
        return 0.0

    total = float(signal.sum())
    if total == 0.0:
        return 0.0
    concentration = float(signal[boundaries].sum() / total)
    baseline = min(0.95, boundaries.size / max(1, signal.size))
    if baseline >= 1.0:
        return 0.0
    return max(0.0, (concentration - baseline) / (1.0 - baseline))


def _to_pil(image_array: np.ndarray) -> Image.Image:
    mode = "RGBA" if image_array.shape[2] == 4 else "RGB"
    return Image.fromarray(image_array, mode=mode)


def _hypothesis_metadata(hypothesis: GridHypothesis) -> dict[str, object]:
    return {
        "target_size": [hypothesis.target_width, hypothesis.target_height],
        "scale_x": round(hypothesis.scale_x, 6),
        "scale_y": round(hypothesis.scale_y, 6),
        "score": round(hypothesis.score, 6),
        "components": {
            key: round(value, 6) for key, value in hypothesis.components.items()
        },
    }


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
