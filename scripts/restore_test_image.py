from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "packages" / "core"
sys.path.insert(0, str(CORE_PATH))

from pixelreforge_core import RestoreSettings, process_image_file  # noqa: E402
from pixelreforge_core.image_io import save_image  # noqa: E402


INPUT_PATH = ROOT / "tests" / "fixtures" / "test-image.jpg"
OUTPUT_PATH = ROOT / "tests" / "output" / "restored-test-image.png"


def main() -> None:
    # The current real fixture is a JPEG with strong compression noise, so the
    # first visual smoke run uses an explicit scale while auto-detection remains
    # covered by synthetic tests.
    result = process_image_file(INPUT_PATH, RestoreSettings(manual_scale_x=4, manual_scale_y=4))
    save_image(result.image, OUTPUT_PATH)

    print(f"input: {INPUT_PATH}")
    print(f"output: {OUTPUT_PATH}")
    print(f"source_size: {result.source_size}")
    print(f"target_size: {result.target_size}")
    print(f"scale: {result.scale.scale_x}x{result.scale.scale_y}")
    print(f"confidence: {result.scale.confidence:.3f}")
    for warning in result.warnings:
        print(f"warning: {warning}")


if __name__ == "__main__":
    main()
