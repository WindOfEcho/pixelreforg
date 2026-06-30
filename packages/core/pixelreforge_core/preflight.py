from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class PreflightAnalysis:
    source_format: str | None
    noise_score: float
    jpeg_artifact_score: float
    ai_artifact_score: float
    grid_confidence: float
    unique_color_count: int
    estimated_palette_size: int
    near_duplicate_color_ratio: float
    recommended_algorithm: str
    recommendation_confidence: float
    recommendation_reason: tuple[str, ...]

    def to_metadata(self) -> dict[str, object]:
        data = asdict(self)
        data["recommendation_reason"] = list(self.recommendation_reason)
        return data


def analyze_image(image_array: np.ndarray, source_format: str | None, grid_confidence: float) -> PreflightAnalysis:
    sample = _sample_pixels(image_array)
    unique_color_count = _unique_color_count(sample)
    estimated_palette_size = _estimated_palette_size(sample)
    near_duplicate_ratio = _near_duplicate_color_ratio(unique_color_count, estimated_palette_size)
    noise_score = _noise_score(image_array, unique_color_count, estimated_palette_size)
    jpeg_score = _jpeg_artifact_score(source_format, noise_score, near_duplicate_ratio)
    ai_score = _ai_artifact_score(source_format, noise_score, near_duplicate_ratio, grid_confidence)
    recommended_algorithm, confidence, reasons = _recommend_algorithm(jpeg_score, ai_score, grid_confidence)

    return PreflightAnalysis(
        source_format=source_format,
        noise_score=noise_score,
        jpeg_artifact_score=jpeg_score,
        ai_artifact_score=ai_score,
        grid_confidence=_clamp01(grid_confidence),
        unique_color_count=unique_color_count,
        estimated_palette_size=estimated_palette_size,
        near_duplicate_color_ratio=near_duplicate_ratio,
        recommended_algorithm=recommended_algorithm,
        recommendation_confidence=confidence,
        recommendation_reason=tuple(reasons),
    )


def _sample_pixels(image_array: np.ndarray, max_pixels: int = 65_536) -> np.ndarray:
    pixels = image_array.reshape(-1, image_array.shape[2])
    if pixels.shape[0] <= max_pixels:
        return pixels
    step = max(1, pixels.shape[0] // max_pixels)
    return pixels[::step][:max_pixels]


def _unique_color_count(pixels: np.ndarray) -> int:
    return int(np.unique(pixels, axis=0).shape[0])


def _estimated_palette_size(pixels: np.ndarray) -> int:
    quantized = (pixels[:, :3] // 16).astype(np.uint8, copy=False)
    if pixels.shape[1] == 4:
        alpha = (pixels[:, 3:4] // 32).astype(np.uint8, copy=False)
        quantized = np.concatenate((quantized, alpha), axis=1)
    return int(np.unique(quantized, axis=0).shape[0])


def _near_duplicate_color_ratio(unique_color_count: int, estimated_palette_size: int) -> float:
    if unique_color_count <= 0:
        return 0.0
    return _clamp01(1.0 - (estimated_palette_size / unique_color_count))


def _noise_score(image_array: np.ndarray, unique_color_count: int, estimated_palette_size: int) -> float:
    pixel_count = max(1, image_array.shape[0] * image_array.shape[1])
    unique_density = min(1.0, unique_color_count / min(pixel_count, 4096))
    palette_fragmentation = _near_duplicate_color_ratio(unique_color_count, estimated_palette_size)
    edge_noise = _edge_noise_score(image_array)
    return _clamp01((unique_density * 0.35) + (palette_fragmentation * 0.45) + (edge_noise * 0.20))


def _edge_noise_score(image_array: np.ndarray) -> float:
    data = image_array[:, :, :3].astype(np.int16, copy=False)
    if data.shape[0] < 2 or data.shape[1] < 2:
        return 0.0

    dx = np.abs(data[:, 1:, :] - data[:, :-1, :]).mean(axis=2)
    dy = np.abs(data[1:, :, :] - data[:-1, :, :]).mean(axis=2)
    weak_edges = (np.count_nonzero((dx > 2) & (dx < 28)) + np.count_nonzero((dy > 2) & (dy < 28)))
    total_edges = dx.size + dy.size
    return _clamp01(weak_edges / max(1, total_edges))


def _jpeg_artifact_score(source_format: str | None, noise_score: float, near_duplicate_ratio: float) -> float:
    format_score = 0.55 if (source_format or "").upper() in ("JPEG", "JPG") else 0.0
    return _clamp01(format_score + (noise_score * 0.30) + (near_duplicate_ratio * 0.15))


def _ai_artifact_score(
    source_format: str | None,
    noise_score: float,
    near_duplicate_ratio: float,
    grid_confidence: float,
) -> float:
    non_jpeg_bias = 0.15 if (source_format or "").upper() not in ("JPEG", "JPG") else 0.0
    uncertain_grid = 1.0 - _clamp01(grid_confidence)
    return _clamp01(non_jpeg_bias + (noise_score * 0.45) + (near_duplicate_ratio * 0.25) + (uncertain_grid * 0.15))


def _recommend_algorithm(jpeg_score: float, ai_score: float, grid_confidence: float) -> tuple[str, float, list[str]]:
    reasons: list[str] = []
    noisy_score = max(jpeg_score, ai_score)
    if noisy_score >= 0.55:
        if jpeg_score >= ai_score:
            reasons.append("JPEG-like artifacts detected")
        else:
            reasons.append("AI/noisy pixel-art artifacts detected")
        if grid_confidence < 0.65:
            reasons.append("integer grid confidence is low")
        reasons.append("many near-duplicate colors or weak color shifts detected")
        return "noisy-pixel-v1", _clamp01(noisy_score), reasons

    reasons.append("clean integer grid is the safest available path")
    return "integer-grid-v1", _clamp01(max(grid_confidence, 0.5)), reasons


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
