from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from pixelreforge_core import RestoreSettings, process_image


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.regression
AI_FIXTURE_NAMES = [path.name for path in sorted((ROOT / "tests" / "fixtures").glob("test-ai-*.png"))]


@pytest.mark.parametrize("fixture_name", AI_FIXTURE_NAMES)
def test_ai_fixtures_auto_pipeline_returns_metadata_without_crashing(fixture_name: str) -> None:
    image = Image.open(ROOT / "tests" / "fixtures" / fixture_name)
    image.thumbnail((256, 256))

    result = process_image(image, RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=16))

    assert result.image.size[0] >= 1
    assert result.image.size[1] >= 1
    assert result.analysis is not None
    assert result.analysis["unique_color_count"] > 0
    assert result.algorithm_used == "ai-pixel-v2"
    assert result.analysis["recommended_algorithm"] == "ai-pixel-v2"
    assert result.analysis["ai_pixel_v2_score"] >= 0.70
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
    assert custom.reconstruction["resize_method"] in {"dominant-color-cluster", "resampled-grid-dominant-color-cluster"}
    assert custom.palette["cleanup_applied"] is True
    assert custom.palette["color_count_after"] <= off.palette["color_count_after"]
    assert len(np.asarray(custom.image).shape) == 3
