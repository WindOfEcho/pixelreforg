from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from pixelreforge_core import RestoreSettings, process_image  # noqa: E402
from pixelreforge_core.image_io import save_image  # noqa: E402


class CoreRestoreTests(unittest.TestCase):
    def test_detects_integer_scale_and_restores_synthetic_pixel_art(self) -> None:
        original = self._make_synthetic_pixel_art()

        for scale in (2, 3, 4):
            with self.subTest(scale=scale):
                enlarged = np.repeat(np.repeat(original, scale, axis=0), scale, axis=1)
                result = process_image(Image.fromarray(enlarged, mode="RGB"), RestoreSettings(max_scale=8))

                self.assertEqual(scale, result.scale.scale_x)
                self.assertEqual(scale, result.scale.scale_y)
                self.assertEqual((original.shape[1], original.shape[0]), result.target_size)
                np.testing.assert_array_equal(original, np.asarray(result.image))

    def test_processes_real_fixture_and_writes_preview_output(self) -> None:
        input_path = ROOT / "tests" / "fixtures" / "test-jpegs-x4-90.jpg"
        output_path = ROOT / "tests" / "output" / "restored-test-image.png"

        image = Image.open(input_path).convert("RGB")
        result = process_image(image, RestoreSettings(scale_mode="manual", manual_scale_x=4, manual_scale_y=4))
        save_image(result.image, output_path)

        self.assertTrue(output_path.exists())
        self.assertEqual((32, 32), result.target_size)
        self.assertLess(result.target_size[0], result.source_size[0])
        self.assertLess(result.target_size[1], result.source_size[1])
        self.assertEqual(4, result.scale.scale_x)
        self.assertEqual(4, result.scale.scale_y)

    def test_restores_integer_scale_png_fixtures_to_original_pixels(self) -> None:
        original = Image.open(ROOT / "tests" / "fixtures" / "test-original.png").convert("RGBA")
        expected = np.asarray(original)

        for fixture_name, scale in (("test-x4.png", 4), ("test-x10.png", 10)):
            with self.subTest(fixture=fixture_name):
                image = Image.open(ROOT / "tests" / "fixtures" / fixture_name)
                result = process_image(image, RestoreSettings(scale_mode="auto", min_scale=2, max_scale=16))

                self.assertEqual((32, 32), result.target_size)
                self.assertEqual(scale, result.scale.scale_x)
                self.assertEqual(scale, result.scale.scale_y)
                self.assertGreaterEqual(result.scale.confidence, 0.99)
                np.testing.assert_array_equal(expected, np.asarray(result.image.convert("RGBA")))

    def test_restores_integer_scale_jpeg_fixtures_to_original_size_with_bounded_error(self) -> None:
        expected = np.asarray(self._original_on_white_background())

        cases = (
            ("test-jpegs-x4-60.jpg", 4),
            ("test-jpegs-x4-90.jpg", 4),
            ("test-jpegs-x10-60.jpg", 10),
            ("test-jpegs-x10-90.jpg", 10),
        )
        for fixture_name, scale in cases:
            with self.subTest(fixture=fixture_name):
                image = Image.open(ROOT / "tests" / "fixtures" / fixture_name)
                result = process_image(image, RestoreSettings(scale_mode="auto", min_scale=2, max_scale=16))
                restored = np.asarray(result.image.convert("RGB"))

                self.assertEqual((32, 32), result.target_size)
                self.assertEqual(scale, result.scale.scale_x)
                self.assertEqual(scale, result.scale.scale_y)
                self.assertGreaterEqual(result.scale.confidence, 0.45)
                self.assertLessEqual(self._mean_absolute_error(restored, expected), 10.0)

    def test_keeps_unscaled_jpeg_fixture_at_original_size_with_low_confidence_warning(self) -> None:
        image = Image.open(ROOT / "tests" / "fixtures" / "test-jpegs-x1-90.jpg")

        result = process_image(image, RestoreSettings(scale_mode="auto", min_scale=2, max_scale=16))

        self.assertEqual((32, 32), result.target_size)
        self.assertEqual(1, result.scale.scale_x)
        self.assertEqual(1, result.scale.scale_y)
        self.assertEqual(0.0, result.scale.confidence)
        self.assertTrue(result.warnings)

    def test_auto_detection_allows_min_scale_one_without_division_by_zero(self) -> None:
        image = Image.open(ROOT / "tests" / "fixtures" / "test-x4.png")

        result = process_image(image, RestoreSettings(scale_mode="auto", min_scale=1, max_scale=16))

        self.assertEqual((32, 32), result.target_size)
        self.assertEqual(4, result.scale.scale_x)
        self.assertEqual(4, result.scale.scale_y)

    def test_resampled_grid_manual_fractional_scale_restores_fixture(self) -> None:
        original = Image.open(ROOT / "tests" / "fixtures" / "test-original.png").convert("RGBA")
        expected = np.asarray(original)

        for fixture_name in ("test-x3.6.png", "test-x6.3.png"):
            with self.subTest(fixture=fixture_name):
                image = Image.open(ROOT / "tests" / "fixtures" / fixture_name)
                scale = image.size[0] / original.size[0]
                result = process_image(
                    image,
                    RestoreSettings(
                        algorithm="resampled-grid-v2",
                        scale_mode="manual",
                        manual_scale_x=scale,
                        manual_scale_y=scale,
                    ),
                )

                self.assertEqual("resampled-grid-v2", result.algorithm_used)
                self.assertEqual((32, 32), result.target_size)
                self.assertAlmostEqual(scale, result.scale.scale_x)
                np.testing.assert_array_equal(expected, np.asarray(result.image.convert("RGBA")))

    def test_resampled_grid_original_size_override_restores_fractional_fixture(self) -> None:
        image = Image.open(ROOT / "tests" / "fixtures" / "test-x3.6.png")

        result = process_image(
            image,
            RestoreSettings(algorithm="resampled-grid-v2", original_width=32, original_height=32),
        )

        self.assertEqual((32, 32), result.target_size)
        self.assertEqual((32, 32), result.original_size_override)
        self.assertEqual("original-size-override", result.scale.method)
        self.assertAlmostEqual(image.size[0] / 32, result.scale.scale_x)

    def test_noisy_pixel_manual_fractional_scale_uses_resampled_cluster_grid(self) -> None:
        image = Image.open(ROOT / "tests" / "fixtures" / "test-x3.6.png")
        scale = image.size[0] / 32

        result = process_image(
            image,
            RestoreSettings(
                algorithm="noisy-pixel-v1",
                scale_mode="manual",
                manual_scale_x=scale,
                manual_scale_y=scale,
            ),
        )

        self.assertEqual("noisy-pixel-v1", result.algorithm_used)
        self.assertEqual((32, 32), result.target_size)
        self.assertEqual("resampled-grid-dominant-color-cluster", result.reconstruction["resize_method"])

    def _make_synthetic_pixel_art(self) -> np.ndarray:
        image = np.full((12, 14, 3), [186, 204, 142], dtype=np.uint8)
        image[2:10, 3:11] = [40, 36, 55]
        image[3:5, 4:6] = [230, 230, 220]
        image[3:5, 8:10] = [230, 230, 220]
        image[6:8, 5:9] = [164, 62, 74]
        image[9:12, 1:4] = [82, 130, 116]
        image[0:2, 10:14] = [219, 181, 146]
        return image

    def _original_on_white_background(self) -> Image.Image:
        original = Image.open(ROOT / "tests" / "fixtures" / "test-original.png").convert("RGBA")
        background = Image.new("RGBA", original.size, (255, 255, 255, 255))
        background.alpha_composite(original)
        return background.convert("RGB")

    def _mean_absolute_error(self, actual: np.ndarray, expected: np.ndarray) -> float:
        return float(np.mean(np.abs(actual.astype(np.int16) - expected.astype(np.int16))))


if __name__ == "__main__":
    unittest.main()
