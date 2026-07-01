import numpy as np

from .models import RestoreSettings, ScaleEstimate


def detect_scale(image_array: np.ndarray, settings: RestoreSettings) -> ScaleEstimate:
    height, width = image_array.shape[:2]
    if settings.original_width is not None and settings.original_height is not None:
        if settings.original_width < 1 or settings.original_height < 1:
            raise ValueError("Original size override must be positive.")
        return ScaleEstimate(
            width / settings.original_width,
            height / settings.original_height,
            1.0,
            1.0,
            "original-size-override",
        )

    if settings.scale_mode == "manual":
        scale_x = settings.manual_scale_x or settings.manual_scale_y
        scale_y = settings.manual_scale_y or settings.manual_scale_x
        if scale_x is None or scale_y is None:
            raise ValueError("Manual scale settings must resolve to both axes.")
        return ScaleEstimate(scale_x, scale_y, 1.0, 1.0, "manual")
    if settings.scale_mode != "auto":
        raise ValueError(f"Unsupported scale mode: {settings.scale_mode}")

    max_scale_x = min(settings.max_scale, max(1, width // 2))
    max_scale_y = min(settings.max_scale, max(1, height // 2))

    horizontal_signal = _boundary_signal(image_array, axis="x")
    vertical_signal = _boundary_signal(image_array, axis="y")

    if settings.algorithm in ("resampled-grid-v2", "noisy-pixel-v1"):
        scale_x, confidence_x = _best_fractional_scale(horizontal_signal, width, settings.min_scale, max_scale_x, settings.fractional_scale_step)
        scale_y, confidence_y = _best_fractional_scale(vertical_signal, height, settings.min_scale, max_scale_y, settings.fractional_scale_step)
        return ScaleEstimate(scale_x, scale_y, confidence_x, confidence_y, "fractional-boundary-energy")

    scale_x, confidence_x = _best_scale(horizontal_signal, width, settings.min_scale, max_scale_x)
    scale_y, confidence_y = _best_scale(vertical_signal, height, settings.min_scale, max_scale_y)

    return ScaleEstimate(scale_x, scale_y, confidence_x, confidence_y, "periodic-boundary-energy")


def _boundary_signal(image_array: np.ndarray, axis: str) -> np.ndarray:
    data = image_array.astype(np.int16, copy=False)
    if axis == "x":
        diff = np.abs(data[:, 1:, :] - data[:, :-1, :]).sum(axis=2)
        return diff.sum(axis=0).astype(np.float64)
    if axis == "y":
        diff = np.abs(data[1:, :, :] - data[:-1, :, :]).sum(axis=2)
        return diff.sum(axis=1).astype(np.float64)
    raise ValueError(f"Unsupported axis: {axis}")


def _best_scale(signal: np.ndarray, image_size: int, min_scale: int, max_scale: int) -> tuple[int, float]:
    if signal.size == 0 or max_scale < min_scale or float(signal.sum()) == 0.0:
        return 1, 0.0

    best_scale = 1
    best_confidence = 0.0

    for scale in range(min_scale, max_scale + 1):
        confidence = _scale_confidence(signal, scale)
        if image_size % scale != 0:
            confidence *= 0.75

        if confidence >= best_confidence and confidence >= 0.2:
            best_scale = scale
            best_confidence = confidence

    return best_scale, min(1.0, best_confidence)


def _scale_confidence(signal: np.ndarray, scale: int) -> float:
    if scale <= 1:
        return 0.0

    buckets = np.array([signal[offset::scale].sum() for offset in range(scale)], dtype=np.float64)
    total = float(buckets.sum())
    if total == 0.0:
        return 0.0

    concentration = float(buckets.max() / total)
    baseline = 1.0 / scale
    return max(0.0, (concentration - baseline) / (1.0 - baseline))


def _best_fractional_scale(signal: np.ndarray, image_size: int, min_scale: int, max_scale: int, scale_step: float) -> tuple[float, float]:
    if signal.size == 0 or max_scale < min_scale or float(signal.sum()) == 0.0:
        return 1.0, 0.0

    step = max(0.05, float(scale_step))
    best_scale = 1.0
    best_confidence = 0.0
    candidate_count = int(np.floor((max_scale - min_scale) / step)) + 1
    for index in range(max(1, candidate_count)):
        scale = min_scale + (index * step)
        if scale > max_scale + 1e-9:
            break
        target_size = max(1, int(round(image_size / scale)))
        confidence = _target_size_confidence(signal, image_size, target_size)
        if confidence >= 0.2 and (confidence > best_confidence + 0.02 or (abs(confidence - best_confidence) <= 0.02 and scale > best_scale)):
            best_scale = image_size / target_size
            best_confidence = confidence

    return best_scale, min(1.0, best_confidence)


def _target_size_confidence(signal: np.ndarray, image_size: int, target_size: int) -> float:
    if target_size <= 1 or target_size >= image_size:
        return 0.0

    boundaries = np.rint(np.arange(1, target_size) * image_size / target_size).astype(np.int64) - 1
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

