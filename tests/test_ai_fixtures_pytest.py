from pathlib import Path
import sys

import numpy as np
from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from pixelreforge_core import RestoreSettings, process_image  # noqa: E402


@pytest.mark.parametrize("fixture_name", ["test-ai-1.png", "test-ai-2.png"])
def test_ai_fixtures_auto_pipeline_returns_metadata_without_crashing(fixture_name: str) -> None:
    image = Image.open(ROOT / "tests" / "fixtures" / fixture_name)

    result = process_image(image, RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=16))

    assert result.image.size[0] >= 1
    assert result.image.size[1] >= 1
    assert result.analysis is not None
    assert result.analysis["unique_color_count"] > 0
    assert result.analysis["recommended_algorithm"] in {"integer-grid-v1", "noisy-pixel-v1"}
    assert result.palette is not None
    assert "color_count_after" in result.palette


def test_ai_fixture_two_noisy_pixel_custom_palette_can_reduce_colors() -> None:
    image = Image.open(ROOT / "tests" / "fixtures" / "test-ai-2.png")
    image.thumbnail((256, 256))

    off = process_image(image, RestoreSettings(algorithm="noisy-pixel-v1", min_scale=1, max_scale=16, palette_cleanup="off"))
    image = Image.open(ROOT / "tests" / "fixtures" / "test-ai-2.png")
    image.thumbnail((256, 256))
    custom = process_image(
        image,
        RestoreSettings(
            algorithm="noisy-pixel-v1",
            min_scale=1,
            max_scale=16,
            palette_cleanup="custom",
            palette_merge_distance=24,
            palette_target_colors=32,
            noisy_color_bucket_size=20,
        ),
    )

    assert custom.algorithm_used == "noisy-pixel-v1"
    assert custom.reconstruction["resize_method"] == "dominant-color-cluster"
    assert custom.palette["cleanup_applied"] is True
    assert custom.palette["color_count_after"] <= off.palette["color_count_after"]
    assert len(np.asarray(custom.image).shape) == 3
