import numpy as np

from .models import RestoreSettings, ScaleEstimate


def detect_scale(image_array: np.ndarray, settings: RestoreSettings) -> ScaleEstimate:
    if settings.scale_mode == "manual":
        scale_x = settings.manual_scale_x or settings.manual_scale_y
        scale_y = settings.manual_scale_y or settings.manual_scale_x
        if scale_x is None or scale_y is None:
            raise ValueError("Manual scale settings must resolve to both axes.")
        return ScaleEstimate(scale_x, scale_y, 1.0, 1.0, "manual")
    if settings.scale_mode != "auto":
        raise ValueError(f"Unsupported scale mode: {settings.scale_mode}")

    height, width = image_array.shape[:2]
    max_scale_x = min(settings.max_scale, max(1, width // 2))
    max_scale_y = min(settings.max_scale, max(1, height // 2))

    horizontal_signal = _boundary_signal(image_array, axis="x")
    vertical_signal = _boundary_signal(image_array, axis="y")

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
