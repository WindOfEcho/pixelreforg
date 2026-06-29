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
        input_path = ROOT / "tests" / "fixtures" / "test-image.jpg"
        output_path = ROOT / "tests" / "output" / "restored-test-image.png"

        image = Image.open(input_path).convert("RGB")
        result = process_image(image, RestoreSettings(scale_mode="manual", manual_scale_x=4, manual_scale_y=4))
        save_image(result.image, output_path)

        self.assertTrue(output_path.exists())
        self.assertEqual((125, 125), result.target_size)
        self.assertLess(result.target_size[0], result.source_size[0])
        self.assertLess(result.target_size[1], result.source_size[1])
        self.assertEqual(4, result.scale.scale_x)
        self.assertEqual(4, result.scale.scale_y)

    def _make_synthetic_pixel_art(self) -> np.ndarray:
        image = np.full((12, 14, 3), [186, 204, 142], dtype=np.uint8)
        image[2:10, 3:11] = [40, 36, 55]
        image[3:5, 4:6] = [230, 230, 220]
        image[3:5, 8:10] = [230, 230, 220]
        image[6:8, 5:9] = [164, 62, 74]
        image[9:12, 1:4] = [82, 130, 116]
        image[0:2, 10:14] = [219, 181, 146]
        return image


if __name__ == "__main__":
    unittest.main()
