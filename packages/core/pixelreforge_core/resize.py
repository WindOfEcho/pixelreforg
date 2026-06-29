from PIL import Image
import numpy as np


def downscale_by_majority_vote(image_array: np.ndarray, scale_x: int, scale_y: int) -> Image.Image:
    if scale_x < 1 or scale_y < 1:
        raise ValueError("Scale values must be positive integers.")

    height, width = image_array.shape[:2]
    target_width = width // scale_x
    target_height = height // scale_y
    if target_width < 1 or target_height < 1:
        raise ValueError("Scale is too large for the input image.")

    cropped = image_array[: target_height * scale_y, : target_width * scale_x]
    channels = cropped.shape[2]
    output = np.empty((target_height, target_width, channels), dtype=np.uint8)

    for y in range(target_height):
        for x in range(target_width):
            block = cropped[y * scale_y : (y + 1) * scale_y, x * scale_x : (x + 1) * scale_x]
            output[y, x] = _most_common_color(block)

    mode = "RGBA" if channels == 4 else "RGB"
    return Image.fromarray(output, mode=mode)


def _most_common_color(block: np.ndarray) -> np.ndarray:
    pixels = block.reshape(-1, block.shape[2])
    colors, counts = np.unique(pixels, axis=0, return_counts=True)
    return colors[int(np.argmax(counts))]
