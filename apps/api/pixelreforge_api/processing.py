from pathlib import Path
import logging
import time

from pixelreforge_core import ProcessingCancelled, RestoreSettings, process_image_file
from pixelreforge_core.image_io import save_image

from .logging_context import reset_request_id, set_request_id
from .models import JobMetadata
from .storage import ROOT, get_job_dir, read_metadata, update_metadata, write_metadata


logger = logging.getLogger(__name__)


def process_job(
    job_id: str,
    algorithm: str = "auto",
    scale_mode: str = "manual",
    manual_scale: float | None = 4,
    min_scale: int = 2,
    max_scale: int = 16,
    original_width: int | None = None,
    original_height: int | None = None,
    palette_cleanup: str = "off",
    palette_merge_distance: float | None = None,
    palette_target_colors: int | None = None,
    noisy_color_bucket_size: int = 16,
    confidence_threshold: float = 0.45,
    fractional_scale_step: float = 0.25,
    request_id: str | None = None,
) -> None:
    token = set_request_id(request_id) if request_id is not None else None
    started = time.perf_counter()
    metadata = read_metadata(job_id)
    if metadata is None:
        logger.warning("Job metadata missing.", extra={"event": "job_metadata_missing", "job_id": job_id})
        if token is not None:
            reset_request_id(token)
        return

    try:
        if metadata.status == "cancelled":
            logger.info("Job was already cancelled.", extra={"event": "job_cancelled", "job_id": job_id, "status": metadata.status})
            return
        logger.info("Job processing started.", extra={"event": "job_processing_started", "job_id": job_id, "status": metadata.status})
        metadata.status = "processing"
        metadata.progress_percent = 10.0
        metadata.stage = "preflight"
        metadata.stage_message = "Preflight analysis..."
        write_metadata(metadata)
        logger.info("Job status changed.", extra={"event": "job_status_changed", "job_id": job_id, "status": metadata.status, "stage": "processing"})

        input_path = ROOT / metadata.input_path
        output_path = get_job_dir(job_id) / "output.png"
        settings = RestoreSettings(
            algorithm=algorithm,
            scale_mode=scale_mode,
            manual_scale_x=manual_scale,
            manual_scale_y=manual_scale,
            min_scale=min_scale,
            max_scale=max_scale,
            original_width=original_width,
            original_height=original_height,
            palette_cleanup=palette_cleanup,
            palette_merge_distance=palette_merge_distance,
            palette_target_colors=palette_target_colors,
            noisy_color_bucket_size=noisy_color_bucket_size,
            confidence_threshold=confidence_threshold,
            fractional_scale_step=fractional_scale_step,
        )
        result = process_image_file(input_path, settings, progress=_progress_callback(job_id), cancel=_cancel_callback(job_id))
        latest_metadata = read_metadata(job_id)
        if latest_metadata is not None and latest_metadata.status == "cancelled":
            logger.info("Job cancelled after processing.", extra={"event": "job_cancelled", "job_id": job_id, "status": latest_metadata.status, "stage": "after_processing"})
            return
        _set_progress(job_id, "save_result", 95.0, "Saving result...")
        save_image(result.image, output_path)
        metadata = read_metadata(job_id) or metadata
        if metadata.status == "cancelled":
            logger.info("Job cancelled after saving.", extra={"event": "job_cancelled", "job_id": job_id, "status": metadata.status, "stage": "after_saving"})
            return

        metadata.status = "completed"
        metadata.progress_percent = 100.0
        metadata.stage = "completed"
        metadata.stage_message = "Restoration complete."
        metadata.output_path = str(output_path.relative_to(ROOT))
        metadata.algorithm_requested = result.algorithm_requested
        metadata.algorithm_used = result.algorithm_used
        metadata.algorithm_version = result.algorithm_version
        metadata.source_size = result.source_size
        metadata.target_size = result.target_size
        metadata.original_size_override = result.original_size_override
        metadata.scale_x = result.scale.scale_x
        metadata.scale_y = result.scale.scale_y
        metadata.scale_method = result.scale.method
        metadata.confidence = result.scale.confidence
        metadata.palette_cleanup = result.palette_cleanup
        metadata.analysis = result.analysis
        metadata.palette = result.palette
        metadata.reconstruction = result.reconstruction
        metadata.warnings = list(result.warnings)
        metadata.error = None
        write_metadata(metadata)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "Job processing completed.",
            extra={
                "event": "job_processing_completed",
                "job_id": job_id,
                "status": metadata.status,
                "stage": "completed",
                "duration_ms": duration_ms,
                "algorithm_used": metadata.algorithm_used,
                "scale_x": metadata.scale_x,
                "scale_y": metadata.scale_y,
                "source_size": metadata.source_size,
                "target_size": metadata.target_size,
                "resize_method": (metadata.reconstruction or {}).get("resize_method"),
                "warnings_count": len(metadata.warnings),
            },
        )
    except ProcessingCancelled:
        latest_metadata = read_metadata(job_id) or metadata
        latest_metadata.status = "cancelled"
        latest_metadata.progress_percent = min(latest_metadata.progress_percent, 99.0)
        latest_metadata.stage = "cancelled"
        latest_metadata.stage_message = "Restoration cancelled."
        latest_metadata.error = None
        write_metadata(latest_metadata)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "Job processing cancelled.",
            extra={"event": "job_processing_cancelled", "job_id": job_id, "status": latest_metadata.status, "stage": "cancelled", "duration_ms": duration_ms},
        )
    except Exception as exc:  # pragma: no cover - metadata path is tested through API failures later.
        latest_metadata = read_metadata(job_id)
        if latest_metadata is not None and latest_metadata.status == "cancelled":
            latest_metadata.error = None
            latest_metadata.stage = "cancelled"
            latest_metadata.stage_message = "Restoration cancelled."
            write_metadata(latest_metadata)
            return
        metadata.status = "failed"
        metadata.stage = "failed"
        metadata.stage_message = "Restoration failed."
        metadata.error = str(exc)
        write_metadata(metadata)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.exception(
            "Job processing failed.",
            extra={
                "event": "job_processing_failed",
                "job_id": job_id,
                "status": metadata.status,
                "stage": "failed",
                "duration_ms": duration_ms,
                "error_type": type(exc).__name__,
            },
        )
    finally:
        if token is not None:
            reset_request_id(token)


def output_file_path(metadata: JobMetadata) -> Path | None:
    if metadata.output_path is None:
        return None
    return ROOT / metadata.output_path


def _progress_callback(job_id: str):  # type: ignore[no-untyped-def]
    def progress(stage: str, percent: float, message: str) -> None:
        _set_progress(job_id, stage, percent, message)

    return progress


def _set_progress(job_id: str, stage: str, percent: float, message: str) -> None:
    def update(metadata: JobMetadata) -> JobMetadata:
        if metadata.status in ("completed", "failed", "cancelled"):
            return metadata
        metadata.status = "processing"
        metadata.progress_percent = max(0.0, min(99.0, float(percent)))
        metadata.stage = stage
        metadata.stage_message = message
        return metadata

    update_metadata(job_id, update)


def _cancel_callback(job_id: str):  # type: ignore[no-untyped-def]
    def cancel() -> bool:
        metadata = read_metadata(job_id)
        return metadata is not None and metadata.status == "cancelled"

    return cancel
