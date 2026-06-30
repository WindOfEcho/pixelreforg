from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from pixelreforge_core import RestoreSettings, process_image, restore_palette  # noqa: E402


class CorePaletteTests(unittest.TestCase):
    def test_palette_cleanup_off_keeps_pixels_unchanged_and_records_metadata(self) -> None:
        image = Image.open(ROOT / "tests" / "fixtures" / "test-original.png").convert("RGBA")

        result = restore_palette(image, "off")

        np.testing.assert_array_equal(np.asarray(image), np.asarray(result.image))
        self.assertFalse(result.metadata["cleanup_applied"])
        self.assertEqual(result.metadata["color_count_before"], result.metadata["color_count_after"])
        self.assertTrue(result.metadata["top_colors_before"])

    def test_palette_cleanup_merges_near_duplicate_colors(self) -> None:
        data = np.array(
            [
                [[100, 50, 25], [103, 51, 24], [220, 210, 40]],
                [[98, 52, 26], [100, 50, 25], [222, 211, 41]],
            ],
            dtype=np.uint8,
        )
        image = Image.fromarray(data, mode="RGB")

        result = restore_palette(image, "medium")
        cleaned_unique = np.unique(np.asarray(result.image).reshape(-1, 3), axis=0)

        self.assertTrue(result.metadata["cleanup_applied"])
        self.assertLess(cleaned_unique.shape[0], np.unique(data.reshape(-1, 3), axis=0).shape[0])
        self.assertGreater(result.metadata["colors_merged"], 0)

    def test_palette_cleanup_preserves_distinct_alpha_values(self) -> None:
        data = np.array(
            [
                [[100, 50, 25, 255], [102, 51, 26, 255]],
                [[100, 50, 25, 30], [102, 51, 26, 30]],
            ],
            dtype=np.uint8,
        )
        image = Image.fromarray(data, mode="RGBA")

        result = restore_palette(image, "strong")
        alpha_values = set(int(value) for value in np.asarray(result.image)[:, :, 3].reshape(-1))

        self.assertEqual({30, 255}, alpha_values)
        self.assertEqual("RGBA", result.image.mode)

    def test_jpeg_palette_cleanup_reduces_restored_color_count(self) -> None:
        image = Image.open(ROOT / "tests" / "fixtures" / "test-jpegs-x4-60.jpg")
        off = process_image(image, RestoreSettings(scale_mode="manual", manual_scale_x=4, manual_scale_y=4, palette_cleanup="off"))
        image = Image.open(ROOT / "tests" / "fixtures" / "test-jpegs-x4-60.jpg")
        cleaned = process_image(image, RestoreSettings(scale_mode="manual", manual_scale_x=4, manual_scale_y=4, palette_cleanup="medium"))

        self.assertLessEqual(cleaned.palette["color_count_after"], off.palette["color_count_after"])
        self.assertTrue(cleaned.palette["cleanup_applied"])

    def test_palette_target_colors_only_applies_to_custom_cleanup(self) -> None:
        data = np.array(
            [
                [[10, 10, 10], [40, 40, 40], [80, 80, 80]],
                [[120, 120, 120], [160, 160, 160], [200, 200, 200]],
            ],
            dtype=np.uint8,
        )
        image = Image.fromarray(data, mode="RGB")

        strong = restore_palette(image, "strong", target_colors=2)
        custom = restore_palette(image, "custom", merge_distance=0, target_colors=2)

        self.assertIsNone(strong.metadata["target_colors"])
        self.assertGreater(strong.metadata["color_count_after"], 2)
        self.assertEqual(2, custom.metadata["target_colors"])
        self.assertLessEqual(custom.metadata["color_count_after"], 2)


if __name__ == "__main__":
    unittest.main()
