from PIL import Image
import numpy as np


def downscale_by_majority_vote(image_array: np.ndarray, scale_x: int, scale_y: int) -> Image.Image:
    if scale_x < 1 or scale_y < 1:
        raise ValueError("Scale values must be positive integers.")

    height, width = image_array.shape[:2]
    if scale_x == 1 and scale_y == 1:
        mode = "RGBA" if image_array.shape[2] == 4 else "RGB"
        return Image.fromarray(image_array.copy(), mode=mode)

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


def downscale_by_dominant_color_cluster(
    image_array: np.ndarray,
    scale_x: int,
    scale_y: int,
    bucket_size: int = 16,
) -> Image.Image:
    if scale_x < 1 or scale_y < 1:
        raise ValueError("Scale values must be positive integers.")

    height, width = image_array.shape[:2]
    if scale_x == 1 and scale_y == 1:
        mode = "RGBA" if image_array.shape[2] == 4 else "RGB"
        return Image.fromarray(image_array.copy(), mode=mode)

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
            output[y, x] = _dominant_color_cluster(block, bucket_size)

    mode = "RGBA" if channels == 4 else "RGB"
    return Image.fromarray(output, mode=mode)


def downscale_by_resampled_grid(
    image_array: np.ndarray,
    target_width: int,
    target_height: int,
    aggregation: str = "majority",
    bucket_size: int = 16,
) -> Image.Image:
    height, width = image_array.shape[:2]
    if target_width < 1 or target_height < 1:
        raise ValueError("Target size must be positive.")
    if target_width > width or target_height > height:
        raise ValueError("Target size must not exceed input size.")

    channels = image_array.shape[2]
    output = np.empty((target_height, target_width, channels), dtype=np.uint8)

    for y in range(target_height):
        y0 = int(np.floor(y * height / target_height))
        y1 = int(np.ceil((y + 1) * height / target_height))
        for x in range(target_width):
            x0 = int(np.floor(x * width / target_width))
            x1 = int(np.ceil((x + 1) * width / target_width))
            block = image_array[y0:max(y0 + 1, y1), x0:max(x0 + 1, x1)]
            if aggregation == "dominant-color-cluster":
                output[y, x] = _dominant_color_cluster(block, bucket_size)
            else:
                output[y, x] = _most_common_color(block)

    mode = "RGBA" if channels == 4 else "RGB"
    return Image.fromarray(output, mode=mode)


def _most_common_color(block: np.ndarray) -> np.ndarray:
    pixels = block.reshape(-1, block.shape[2])
    colors, counts = np.unique(pixels, axis=0, return_counts=True)
    return colors[int(np.argmax(counts))]


def _dominant_color_cluster(block: np.ndarray, bucket_size: int) -> np.ndarray:
    pixels = block.reshape(-1, block.shape[2])
    bucket_size = max(1, int(bucket_size))
    quantized = pixels[:, :3] // bucket_size
    if pixels.shape[1] == 4:
        alpha = pixels[:, 3:4] // max(1, bucket_size * 2)
        quantized = np.concatenate((quantized, alpha), axis=1)

    buckets, inverse, counts = np.unique(quantized, axis=0, return_inverse=True, return_counts=True)
    dominant_bucket = int(np.argmax(counts))
    dominant_pixels = pixels[inverse == dominant_bucket]
    if dominant_pixels.size == 0:
        return _most_common_color(block)

    return np.median(dominant_pixels, axis=0).astype(np.uint8)
