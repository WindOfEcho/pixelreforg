from pathlib import Path

from PIL import Image
import numpy as np

from .image_io import load_image
from .models import ProcessingResult, RestoreSettings
from .resize import downscale_by_majority_vote
from .scale_detection import detect_scale


def process_image(image: Image.Image, settings: RestoreSettings | None = None) -> ProcessingResult:
    settings = settings or RestoreSettings()
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

    source_size = image.size
    image_array = np.asarray(image)
    scale = detect_scale(image_array, settings)

    warnings: list[str] = []
    if scale.confidence < settings.confidence_threshold:
        warnings.append("Low confidence scale detection; use manual scale override if the result looks wrong.")

    restored = downscale_by_majority_vote(image_array, scale.scale_x, scale.scale_y)
    return ProcessingResult(restored, scale, source_size, restored.size, tuple(warnings))


def process_image_file(path: str | Path, settings: RestoreSettings | None = None) -> ProcessingResult:
    return process_image(load_image(path), settings)
