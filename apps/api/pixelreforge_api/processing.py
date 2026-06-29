from pathlib import Path
import sys

from .models import JobMetadata
from .storage import ROOT, get_job_dir, read_metadata, write_metadata


CORE_PATH = ROOT / "packages" / "core"
sys.path.insert(0, str(CORE_PATH))

from pixelreforge_core import RestoreSettings, process_image_file  # noqa: E402
from pixelreforge_core.image_io import save_image  # noqa: E402


def process_job(
    job_id: str,
    scale_mode: str = "manual",
    manual_scale: int | None = 4,
    min_scale: int = 2,
    max_scale: int = 16,
    confidence_threshold: float = 0.45,
) -> None:
    metadata = read_metadata(job_id)
    if metadata is None:
        return

    try:
        if metadata.status == "cancelled":
            return
        metadata.status = "processing"
        write_metadata(metadata)

        input_path = ROOT / metadata.input_path
        output_path = get_job_dir(job_id) / "output.png"
        settings = RestoreSettings(
            scale_mode=scale_mode,
            manual_scale_x=manual_scale,
            manual_scale_y=manual_scale,
            min_scale=min_scale,
            max_scale=max_scale,
            confidence_threshold=confidence_threshold,
        )
        result = process_image_file(input_path, settings)
        latest_metadata = read_metadata(job_id)
        if latest_metadata is not None and latest_metadata.status == "cancelled":
            return
        save_image(result.image, output_path)

        metadata.status = "completed"
        metadata.output_path = str(output_path.relative_to(ROOT))
        metadata.source_size = result.source_size
        metadata.target_size = result.target_size
        metadata.scale_x = result.scale.scale_x
        metadata.scale_y = result.scale.scale_y
        metadata.scale_method = result.scale.method
        metadata.confidence = result.scale.confidence
        metadata.warnings = list(result.warnings)
        metadata.error = None
        write_metadata(metadata)
    except Exception as exc:  # pragma: no cover - metadata path is tested through API failures later.
        metadata.status = "failed"
        metadata.error = str(exc)
        write_metadata(metadata)


def output_file_path(metadata: JobMetadata) -> Path | None:
    if metadata.output_path is None:
        return None
    return ROOT / metadata.output_path
