from pathlib import Path
from dataclasses import replace

from PIL import Image
import numpy as np

from .ai_pixel import restore_ai_pixel_art
from .image_io import load_image
from .models import CancelCallback, ProcessingCancelled, ProcessingResult, ProgressCallback, RestoreSettings, ScaleEstimate
from .palette import restore_palette
from .preflight import PreflightAnalysis, analyze_image
from .resize import downscale_by_dominant_color_cluster, downscale_by_majority_vote, downscale_by_resampled_grid
from .scale_detection import detect_scale


def process_image(
    image: Image.Image,
    settings: RestoreSettings | None = None,
    progress: ProgressCallback | None = None,
    cancel: CancelCallback | None = None,
) -> ProcessingResult:
    settings = settings or RestoreSettings()
    _report_progress(progress, "preflight", 10.0, "Preflight analysis...")
    _raise_if_cancelled(cancel)
    source_format = image.format
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

    source_size = image.size
    image_array = np.asarray(image)
    scale, preflight, algorithm_used, detection_metadata = _select_scale_and_algorithm(image_array, source_format, settings)
    _report_progress(progress, "grid_recovery", 35.0, "Grid recovery...")
    _raise_if_cancelled(cancel)

    warnings: list[str] = []
    if settings.algorithm == "auto" and algorithm_used != preflight.recommended_algorithm and algorithm_used != "resampled-grid-v2":
        warnings.append(
            f"Auto recommended {preflight.recommended_algorithm}, but it is not implemented yet; using {algorithm_used}."
        )
    if scale.confidence < settings.confidence_threshold:
        warnings.append("Low confidence scale detection; use manual scale override if the result looks wrong.")

    _report_progress(progress, "image_reconstruction", 45.0, "Image reconstruction...")
    _raise_if_cancelled(cancel)
    ai_result_metadata: dict[str, object] = {}
    if algorithm_used == "resampled-grid-v2":
        resize_method = "resampled-grid-majority"
        target_width, target_height = _target_size_from_scale(source_size, scale.scale_x, scale.scale_y)
        restored = downscale_by_resampled_grid(image_array, target_width, target_height, cancel=cancel)
    elif algorithm_used in ("ai-pixel-v2", "ai-grid-hypothesis-v1"):
        resize_method = "ai-grid-hypothesis-v1-resampled-cluster" if algorithm_used == "ai-grid-hypothesis-v1" else "ai-pixel-v2-resampled-cluster"
        target_width, target_height = _target_size_from_scale(source_size, scale.scale_x, scale.scale_y)
        ai_result = restore_ai_pixel_art(image_array, target_width, target_height, settings.noisy_color_bucket_size, cancel=cancel)
        ai_result_metadata = ai_result.metadata
        restored = ai_result.image
    elif algorithm_used == "noisy-pixel-v1" and _uses_fractional_grid(scale.scale_x, scale.scale_y):
        resize_method = "resampled-grid-dominant-color-cluster"
        target_width, target_height = _target_size_from_scale(source_size, scale.scale_x, scale.scale_y)
        restored = downscale_by_resampled_grid(
            image_array,
            target_width,
            target_height,
            aggregation="dominant-color-cluster",
            bucket_size=settings.noisy_color_bucket_size,
            cancel=cancel,
        )
    elif algorithm_used == "noisy-pixel-v1":
        resize_method = "dominant-color-cluster"
        restored = downscale_by_dominant_color_cluster(
            image_array,
            int(round(scale.scale_x)),
            int(round(scale.scale_y)),
            settings.noisy_color_bucket_size,
            cancel=cancel,
        )
    else:
        resize_method = "majority-vote"
        restored = downscale_by_majority_vote(image_array, int(round(scale.scale_x)), int(round(scale.scale_y)), cancel=cancel)
    _report_progress(progress, "palette_cleanup", 75.0, "Palette analysis and cleanup...")
    _raise_if_cancelled(cancel)
    palette_result = restore_palette(
        restored,
        settings.palette_cleanup,
        merge_distance=settings.palette_merge_distance,
        target_colors=settings.palette_target_colors,
    )
    _report_progress(progress, "image_reconstruction", 90.0, "Finalizing reconstruction...")
    _raise_if_cancelled(cancel)
    restored = palette_result.image
    warnings.extend(palette_result.warnings)
    original_size_override = None
    if settings.original_width is not None or settings.original_height is not None:
        if settings.original_width is None or settings.original_height is None:
            warnings.append("Original size override requires both width and height; it was ignored.")
        else:
            original_size_override = (settings.original_width, settings.original_height)

    return ProcessingResult(
        image=restored,
        scale=scale,
        source_size=source_size,
        target_size=restored.size,
        algorithm_requested=settings.algorithm,
        algorithm_used=algorithm_used,
        algorithm_version=algorithm_used,
        original_size_override=original_size_override,
        palette_cleanup=settings.palette_cleanup,
        analysis=preflight.to_metadata()
        | {
            "algorithm_selection": {"requested": settings.algorithm, "used": algorithm_used},
            "scale_detection": detection_metadata,
        },
        palette=palette_result.metadata,
        reconstruction={
            "resize_method": resize_method,
            "noisy_color_bucket_size": settings.noisy_color_bucket_size,
            "fractional_scale_step": settings.fractional_scale_step,
        }
        | ai_result_metadata,
        warnings=tuple(warnings),
    )


def process_image_file(
    path: str | Path,
    settings: RestoreSettings | None = None,
    progress: ProgressCallback | None = None,
    cancel: CancelCallback | None = None,
) -> ProcessingResult:
    return process_image(load_image(path), settings, progress=progress, cancel=cancel)


def _report_progress(progress: ProgressCallback | None, stage: str, percent: float, message: str) -> None:
    if progress is not None:
        progress(stage, percent, message)


def _raise_if_cancelled(cancel: CancelCallback | None) -> None:
    if cancel is not None and cancel():
        raise ProcessingCancelled("Processing was cancelled.")


def _resolve_algorithm(settings: RestoreSettings, recommended_algorithm: str) -> str:
    if settings.algorithm == "integer-grid-v1":
        return "integer-grid-v1"
    if settings.algorithm == "noisy-pixel-v1":
        return "noisy-pixel-v1"
    if settings.algorithm == "resampled-grid-v2":
        return "resampled-grid-v2"
    if settings.algorithm == "ai-pixel-v2":
        return "ai-pixel-v2"
    if settings.algorithm == "ai-grid-hypothesis-v1":
        return "ai-grid-hypothesis-v1"
    if settings.algorithm == "auto":
        if recommended_algorithm in ("integer-grid-v1", "resampled-grid-v2", "noisy-pixel-v1", "ai-pixel-v2"):
            return recommended_algorithm
        return "integer-grid-v1"
    raise NotImplementedError(f"Restore algorithm is not implemented yet: {settings.algorithm}")


def _select_scale_and_algorithm(
    image_array: np.ndarray,
    source_format: str | None,
    settings: RestoreSettings,
) -> tuple[ScaleEstimate, PreflightAnalysis, str, dict[str, object]]:
    if settings.algorithm != "auto":
        scale = detect_scale(image_array, settings)
        preflight = analyze_image(image_array, source_format, scale.confidence)
        return scale, preflight, _resolve_algorithm(settings, preflight.recommended_algorithm), _scale_metadata(scale)

    integer_scale = detect_scale(image_array, replace(settings, algorithm="integer-grid-v1"))
    fractional_scale = detect_scale(image_array, replace(settings, algorithm="resampled-grid-v2"))
    preflight = analyze_image(image_array, source_format, max(integer_scale.confidence, fractional_scale.confidence))
    algorithm_used = _resolve_algorithm(settings, preflight.recommended_algorithm)

    if algorithm_used == "integer-grid-v1" and _should_use_fractional(integer_scale, fractional_scale):
        algorithm_used = "resampled-grid-v2"
        scale = fractional_scale
    elif algorithm_used == "noisy-pixel-v1" and fractional_scale.confidence >= integer_scale.confidence:
        scale = fractional_scale
    else:
        scale = integer_scale

    return scale, preflight, algorithm_used, {"integer": _scale_metadata(integer_scale), "fractional": _scale_metadata(fractional_scale)}


def _should_use_fractional(integer_scale: ScaleEstimate, fractional_scale: ScaleEstimate) -> bool:
    if fractional_scale.confidence < 0.2:
        return False
    if fractional_scale.confidence > integer_scale.confidence + 0.05:
        return True
    return integer_scale.confidence < 0.2 and _uses_fractional_grid(fractional_scale.scale_x, fractional_scale.scale_y)


def _scale_metadata(scale: ScaleEstimate) -> dict[str, object]:
    metadata = {
        "scale_x": scale.scale_x,
        "scale_y": scale.scale_y,
        "confidence": scale.confidence,
        "method": scale.method,
    }
    if scale.details is not None:
        metadata["details"] = scale.details
    return metadata


def _target_size_from_scale(source_size: tuple[int, int], scale_x: float, scale_y: float) -> tuple[int, int]:
    width, height = source_size
    target_width = max(1, int(round(width / scale_x)))
    target_height = max(1, int(round(height / scale_y)))
    return target_width, target_height


def _uses_fractional_grid(scale_x: float, scale_y: float) -> bool:
    return abs(scale_x - round(scale_x)) > 1e-6 or abs(scale_y - round(scale_y)) > 1e-6
