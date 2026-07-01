from dataclasses import dataclass

from PIL import Image
import numpy as np

from .resize import downscale_by_resampled_grid


@dataclass(frozen=True)
class AiPixelResult:
    image: Image.Image
    metadata: dict[str, object]


def restore_ai_pixel_art(
    image_array: np.ndarray,
    target_width: int,
    target_height: int,
    bucket_size: int = 16,
) -> AiPixelResult:
    clustered = downscale_by_resampled_grid(
        image_array,
        target_width,
        target_height,
        aggregation="dominant-color-cluster",
        bucket_size=bucket_size,
    )
    cleaned_array, replaced_pixels = _replace_isolated_pixels(np.asarray(clustered))
    mode = "RGBA" if cleaned_array.shape[2] == 4 else "RGB"
    return AiPixelResult(
        image=Image.fromarray(cleaned_array, mode=mode),
        metadata={
            "artifact_cleanup": "isolated-pixel-neighborhood",
            "isolated_pixels_replaced": replaced_pixels,
        },
    )


def _replace_isolated_pixels(image_array: np.ndarray) -> tuple[np.ndarray, int]:
    if image_array.shape[0] < 3 or image_array.shape[1] < 3:
        return image_array.copy(), 0

    output = image_array.copy()
    replaced = 0
    for y in range(1, image_array.shape[0] - 1):
        for x in range(1, image_array.shape[1] - 1):
            block = image_array[y - 1 : y + 2, x - 1 : x + 2]
            center = image_array[y, x]
            neighbors = np.delete(block.reshape(-1, image_array.shape[2]), 4, axis=0)
            colors, counts = np.unique(neighbors, axis=0, return_counts=True)
            dominant_index = int(np.argmax(counts))
            dominant = colors[dominant_index]
            if counts[dominant_index] >= 5 and _color_distance(center, dominant) >= 24.0:
                output[y, x] = dominant
                replaced += 1

    return output, replaced


def _color_distance(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.linalg.norm(left[:3].astype(np.float32) - right[:3].astype(np.float32)))
