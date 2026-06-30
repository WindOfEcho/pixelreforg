from pathlib import Path

from PIL import Image
import numpy as np

from .image_io import load_image
from .models import ProcessingResult, RestoreSettings
from .palette import restore_palette
from .preflight import analyze_image
from .resize import downscale_by_dominant_color_cluster, downscale_by_majority_vote
from .scale_detection import detect_scale


def process_image(image: Image.Image, settings: RestoreSettings | None = None) -> ProcessingResult:
    settings = settings or RestoreSettings()
    source_format = image.format
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

    source_size = image.size
    image_array = np.asarray(image)
    scale = detect_scale(image_array, settings)
    preflight = analyze_image(image_array, source_format, scale.confidence)
    algorithm_used = _resolve_algorithm(settings, preflight.recommended_algorithm)

    warnings: list[str] = []
    if settings.algorithm == "auto" and algorithm_used != preflight.recommended_algorithm:
        warnings.append(
            f"Auto recommended {preflight.recommended_algorithm}, but it is not implemented yet; using {algorithm_used}."
        )
    if scale.confidence < settings.confidence_threshold:
        warnings.append("Low confidence scale detection; use manual scale override if the result looks wrong.")

    resize_method = "dominant-color-cluster" if algorithm_used == "noisy-pixel-v1" else "majority-vote"
    if resize_method == "dominant-color-cluster":
        restored = downscale_by_dominant_color_cluster(
            image_array,
            scale.scale_x,
            scale.scale_y,
            settings.noisy_color_bucket_size,
        )
    else:
        restored = downscale_by_majority_vote(image_array, scale.scale_x, scale.scale_y)
    palette_result = restore_palette(
        restored,
        settings.palette_cleanup,
        merge_distance=settings.palette_merge_distance,
        target_colors=settings.palette_target_colors,
    )
    restored = palette_result.image
    warnings.extend(palette_result.warnings)
    original_size_override = None
    if settings.original_width is not None or settings.original_height is not None:
        if settings.original_width is None or settings.original_height is None:
            warnings.append("Original size override requires both width and height; it was ignored.")
        else:
            original_size_override = (settings.original_width, settings.original_height)
            warnings.append("Original size override is reserved for the next algorithms and was not applied.")

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
        | {"algorithm_selection": {"requested": settings.algorithm, "used": algorithm_used}},
        palette=palette_result.metadata,
        reconstruction={"resize_method": resize_method, "noisy_color_bucket_size": settings.noisy_color_bucket_size},
        warnings=tuple(warnings),
    )


def process_image_file(path: str | Path, settings: RestoreSettings | None = None) -> ProcessingResult:
    return process_image(load_image(path), settings)


def _resolve_algorithm(settings: RestoreSettings, recommended_algorithm: str) -> str:
    if settings.algorithm == "integer-grid-v1":
        return "integer-grid-v1"
    if settings.algorithm == "noisy-pixel-v1":
        return "noisy-pixel-v1"
    if settings.algorithm == "auto":
        if recommended_algorithm in ("integer-grid-v1", "noisy-pixel-v1"):
            return recommended_algorithm
        return "integer-grid-v1"
    raise NotImplementedError(f"Restore algorithm is not implemented yet: {settings.algorithm}")
