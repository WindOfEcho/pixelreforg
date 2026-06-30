from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from pixelreforge_core import RestoreSettings, analyze_image, process_image  # noqa: E402


class CorePreflightTests(unittest.TestCase):
    def test_clean_integer_png_recommends_integer_grid(self) -> None:
        image = Image.open(ROOT / "tests" / "fixtures" / "test-x4.png")
        result = process_image(image, RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=2, max_scale=16))

        self.assertEqual("auto", result.algorithm_requested)
        self.assertEqual("integer-grid-v1", result.algorithm_used)
        self.assertIsNotNone(result.analysis)
        self.assertEqual("integer-grid-v1", result.analysis["recommended_algorithm"])
        self.assertGreaterEqual(result.analysis["grid_confidence"], 0.99)

    def test_noisy_jpeg_auto_uses_noisy_pixel(self) -> None:
        for fixture_name in ("test-jpegs-x4-60.jpg", "test-jpegs-x10-60.jpg"):
            with self.subTest(fixture=fixture_name):
                image = Image.open(ROOT / "tests" / "fixtures" / fixture_name)
                result = process_image(image, RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=2, max_scale=16))

                self.assertEqual("noisy-pixel-v1", result.algorithm_used)
                self.assertIsNotNone(result.analysis)
                self.assertEqual("noisy-pixel-v1", result.analysis["recommended_algorithm"])
                self.assertGreaterEqual(result.analysis["jpeg_artifact_score"], 0.55)
                self.assertEqual("dominant-color-cluster", result.reconstruction["resize_method"])

    def test_explicit_noisy_pixel_algorithm_uses_cluster_resize(self) -> None:
        image = Image.open(ROOT / "tests" / "fixtures" / "test-jpegs-x4-60.jpg")

        result = process_image(image, RestoreSettings(algorithm="noisy-pixel-v1", scale_mode="auto", min_scale=2, max_scale=16))

        self.assertEqual("noisy-pixel-v1", result.algorithm_used)
        self.assertEqual("dominant-color-cluster", result.reconstruction["resize_method"])
        self.assertEqual((32, 32), result.target_size)

    def test_noisy_pixel_manual_scale_can_downscale_ai_fixture(self) -> None:
        image = Image.open(ROOT / "tests" / "fixtures" / "test-ai-2.png")
        image.thumbnail((256, 256))
        source_size = image.size

        result = process_image(
            image,
            RestoreSettings(algorithm="noisy-pixel-v1", scale_mode="manual", manual_scale_x=2, manual_scale_y=2),
        )

        self.assertEqual("noisy-pixel-v1", result.algorithm_used)
        self.assertEqual((source_size[0] // 2, source_size[1] // 2), result.target_size)

    def test_ai_fixtures_get_preflight_scores_without_crashing(self) -> None:
        for fixture_name in ("test-ai-1.png", "test-ai-2.png"):
            with self.subTest(fixture=fixture_name):
                image = Image.open(ROOT / "tests" / "fixtures" / fixture_name)
                analysis = analyze_image(np.asarray(image.convert("RGBA")), image.format, grid_confidence=0.1)

                self.assertGreaterEqual(analysis.noise_score, 0.0)
                self.assertGreaterEqual(analysis.ai_artifact_score, 0.0)
                self.assertGreater(analysis.unique_color_count, 0)
                self.assertIn(analysis.recommended_algorithm, ("integer-grid-v1", "noisy-pixel-v1"))

    def test_palette_cleanup_setting_is_recorded_not_applied(self) -> None:
        image = Image.open(ROOT / "tests" / "fixtures" / "test-x4.png")
        result = process_image(image, RestoreSettings(palette_cleanup="medium", scale_mode="manual", manual_scale_x=4, manual_scale_y=4))

        self.assertEqual("medium", result.palette_cleanup)
        self.assertEqual("medium", result.palette["cleanup_requested"])
        self.assertTrue(result.palette["cleanup_applied"])
        self.assertIn("color_count_before", result.palette)
        self.assertIn("color_count_after", result.palette)


if __name__ == "__main__":
    unittest.main()
