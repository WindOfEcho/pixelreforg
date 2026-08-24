from pathlib import Path
import logging
import time

from pydantic import ValidationError
from pixelreforge_core import ProcessingCancelled, RestoreSettings, process_image_file
from pixelreforge_core.image_io import save_image

from .job_store import JobStore
from .logging_context import reset_request_id, set_request_id
from .models import JobMetadata, JobParameters, SpriteSheetParameters
from .sprite_sheet_processing import process_sprite_sheet_job
from .storage import ROOT, output_file_path_for_job


logger = logging.getLogger(__name__)


def process_job(job_id: str, store: JobStore, request_id: str | None = None) -> None:
    token = set_request_id(request_id) if request_id is not None else None
    started = time.perf_counter()
    metadata = store.get_job(job_id)
    if metadata is None:
        logger.warning("Job metadata missing.", extra={"event": "job_metadata_missing", "job_id": job_id})
        if token is not None:
            reset_request_id(token)
        return

    try:
        if metadata.status == "cancelled" or metadata.cancel_requested:
            _mark_cancelled(store, job_id, metadata)
            logger.info("Job was already cancelled.", extra={"event": "job_cancelled", "job_id": job_id, "status": "cancelled"})
            return

        if metadata.job_type == "sprite_sheet":
            _process_sprite_sheet_job(job_id, store, metadata, started)
            return

        params = JobParameters.model_validate(metadata.params)
        logger.info("Job processing started.", extra={"event": "job_processing_started", "job_id": job_id, "status": metadata.status})
        _set_progress(store, job_id, "preflight", 10.0, "Preflight analysis...")

        input_path = ROOT / metadata.input_path
        output_path = output_file_path_for_job(job_id)
        settings = RestoreSettings(
            algorithm=params.algorithm,
            scale_mode=params.scale_mode,
            manual_scale_x=params.scale,
            manual_scale_y=params.scale,
            min_scale=params.min_scale,
            max_scale=params.max_scale,
            original_width=params.original_width,
            original_height=params.original_height,
            palette_cleanup=params.palette_cleanup,
            palette_merge_distance=params.palette_merge_distance,
            palette_target_colors=params.palette_target_colors,
            noisy_color_bucket_size=params.noisy_color_bucket_size,
            confidence_threshold=params.confidence_threshold,
            fractional_scale_step=params.fractional_scale_step,
        )
        result = process_image_file(input_path, settings, progress=_progress_callback(job_id, store), cancel=_cancel_callback(job_id, store))
        latest_metadata = store.get_job(job_id)
        if latest_metadata is not None and (latest_metadata.status == "cancelled" or latest_metadata.cancel_requested):
            _mark_cancelled(store, job_id, latest_metadata)
            logger.info("Job cancelled after processing.", extra={"event": "job_cancelled", "job_id": job_id, "status": "cancelled", "stage": "after_processing"})
            return

        _set_progress(store, job_id, "save_result", 95.0, "Saving result...")
        save_image(result.image, output_path)
        metadata = store.get_job(job_id) or metadata
        if metadata.status == "cancelled" or metadata.cancel_requested:
            _mark_cancelled(store, job_id, metadata)
            logger.info("Job cancelled after saving.", extra={"event": "job_cancelled", "job_id": job_id, "status": "cancelled", "stage": "after_saving"})
            return

        def complete(current: JobMetadata) -> JobMetadata:
            if current.status == "cancelled" or current.cancel_requested:
                return current
            current.status = "completed"
            current.progress_percent = 100.0
            current.stage = "completed"
            current.stage_message = "Restoration complete."
            current.output_path = str(output_path.relative_to(ROOT))
            current.algorithm_requested = result.algorithm_requested
            current.algorithm_used = result.algorithm_used
            current.algorithm_version = result.algorithm_version
            current.source_size = result.source_size
            current.target_size = result.target_size
            current.original_size_override = result.original_size_override
            current.scale_x = result.scale.scale_x
            current.scale_y = result.scale.scale_y
            current.scale_method = result.scale.method
            current.confidence = result.scale.confidence
            current.palette_cleanup = result.palette_cleanup
            current.analysis = result.analysis
            current.palette = result.palette
            current.reconstruction = result.reconstruction
            current.warnings = list(result.warnings)
            current.error = None
            current.last_error = None
            current.started_at = None
            current.heartbeat_at = None
            current.worker_id = None
            return current

        completed_metadata = store.update_job(job_id, complete) or metadata
        if completed_metadata.status == "cancelled" or completed_metadata.cancel_requested:
            _mark_cancelled(store, job_id, completed_metadata)
            logger.info("Job cancelled before completion.", extra={"event": "job_cancelled", "job_id": job_id, "status": "cancelled"})
            return
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "Job processing completed.",
            extra={
                "event": "job_processing_completed",
                "job_id": job_id,
                "status": completed_metadata.status,
                "stage": "completed",
                "duration_ms": duration_ms,
                "algorithm_used": completed_metadata.algorithm_used,
                "scale_x": completed_metadata.scale_x,
                "scale_y": completed_metadata.scale_y,
                "source_size": completed_metadata.source_size,
                "target_size": completed_metadata.target_size,
                "resize_method": (completed_metadata.reconstruction or {}).get("resize_method"),
                "warnings_count": len(completed_metadata.warnings),
            },
        )
    except ProcessingCancelled:
        latest_metadata = store.get_job(job_id) or metadata
        _mark_cancelled(store, job_id, latest_metadata)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "Job processing cancelled.",
            extra={"event": "job_processing_cancelled", "job_id": job_id, "status": "cancelled", "stage": "cancelled", "duration_ms": duration_ms},
        )
    except Exception as exc:  # pragma: no cover - detailed branches are covered through worker tests.
        latest_metadata = store.get_job(job_id)
        if latest_metadata is not None and (latest_metadata.status == "cancelled" or latest_metadata.cancel_requested):
            _mark_cancelled(store, job_id, latest_metadata)
            return

        failed_metadata = _record_failure(store, job_id, metadata, exc)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.exception(
            "Job processing failed.",
            extra={
                "event": "job_processing_failed",
                "job_id": job_id,
                "status": failed_metadata.status,
                "stage": failed_metadata.stage,
                "duration_ms": duration_ms,
                "error_type": type(exc).__name__,
                "attempts": failed_metadata.attempts,
                "max_attempts": failed_metadata.max_attempts,
            },
        )
    finally:
        if token is not None:
            reset_request_id(token)


def output_file_path(metadata: JobMetadata) -> Path | None:
    if metadata.output_path is None:
        return None
    return ROOT / metadata.output_path


def _process_sprite_sheet_job(job_id: str, store: JobStore, metadata: JobMetadata, started: float) -> None:
    params = SpriteSheetParameters.model_validate(metadata.params)
    logger.info(
        "Sprite-sheet job processing started.",
        extra={"event": "sprite_sheet_processing_started", "job_id": job_id, "input_count": len(metadata.input_paths)},
    )
    _set_progress(store, job_id, "load_inputs", 8.0, "Loading sprite images...")
    output = process_sprite_sheet_job(
        metadata,
        progress=_progress_callback(job_id, store),
        cancel=_cancel_callback(job_id, store),
    )
    latest_metadata = store.get_job(job_id)
    if latest_metadata is not None and (latest_metadata.status == "cancelled" or latest_metadata.cancel_requested):
        _mark_cancelled(store, job_id, latest_metadata)
        logger.info("Sprite-sheet job cancelled after processing.", extra={"event": "sprite_sheet_processing_cancelled", "job_id": job_id})
        return

    _set_progress(store, job_id, "save_result", 97.0, "Saving sprite atlas...")

    def complete(current: JobMetadata) -> JobMetadata:
        if current.status == "cancelled" or current.cancel_requested:
            return current
        current.status = "completed"
        current.progress_percent = 100.0
        current.stage = "completed"
        current.stage_message = "Sprite atlas complete."
        current.output_path = str(output.output_path.relative_to(ROOT))
        current.algorithm_requested = "sprite-sheet"
        current.algorithm_used = params.packing_mode
        current.algorithm_version = "sprite-sheet-v1"
        current.source_size = None
        current.target_size = output.atlas_size
        current.original_size_override = None
        current.scale_x = None
        current.scale_y = None
        current.scale_method = None
        current.confidence = None
        current.palette_cleanup = None
        current.analysis = {
            "frame_count": output.frame_count,
            "input_mode": params.input_mode,
            "packing_mode": params.packing_mode,
            "metadata_available": output.metadata_path is not None,
        }
        current.palette = None
        current.reconstruction = {
            "trim_transparent": params.trim_transparent,
            "padding": params.padding,
            "border_padding": params.border_padding,
            "extrude": params.extrude,
            "power_of_two": params.power_of_two,
        }
        current.warnings = list(output.warnings)
        current.error = None
        current.last_error = None
        current.started_at = None
        current.heartbeat_at = None
        current.worker_id = None
        return current

    completed_metadata = store.update_job(job_id, complete) or metadata
    if completed_metadata.status == "cancelled" or completed_metadata.cancel_requested:
        _mark_cancelled(store, job_id, completed_metadata)
        logger.info("Sprite-sheet job cancelled before completion.", extra={"event": "sprite_sheet_processing_cancelled", "job_id": job_id})
        return
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "Sprite-sheet job processing completed.",
        extra={
            "event": "sprite_sheet_processing_completed",
            "job_id": job_id,
            "status": completed_metadata.status,
            "duration_ms": duration_ms,
            "frame_count": output.frame_count,
            "target_size": output.atlas_size,
        },
    )


def _progress_callback(job_id: str, store: JobStore):  # type: ignore[no-untyped-def]
    def progress(stage: str, percent: float, message: str) -> None:
        _set_progress(store, job_id, stage, percent, message)

    return progress


def _set_progress(store: JobStore, job_id: str, stage: str, percent: float, message: str) -> None:
    def update(metadata: JobMetadata) -> JobMetadata:
        if metadata.status in ("completed", "failed", "cancelled"):
            return metadata
        metadata.status = "processing"
        metadata.progress_percent = max(0.0, min(99.0, float(percent)))
        metadata.stage = stage
        metadata.stage_message = message
        return metadata

    store.update_job(job_id, update)


def _cancel_callback(job_id: str, store: JobStore):  # type: ignore[no-untyped-def]
    def cancel() -> bool:
        metadata = store.get_job(job_id)
        return metadata is not None and (metadata.status == "cancelled" or metadata.cancel_requested)

    return cancel


def _mark_cancelled(store: JobStore, job_id: str, fallback: JobMetadata) -> JobMetadata:
    def update(metadata: JobMetadata) -> JobMetadata:
        metadata.status = "cancelled"
        metadata.progress_percent = min(metadata.progress_percent, 99.0)
        metadata.stage = "cancelled"
        metadata.stage_message = _cancelled_message(metadata)
        metadata.error = None
        metadata.started_at = None
        metadata.heartbeat_at = None
        metadata.worker_id = None
        return metadata

    return store.update_job(job_id, update) or fallback


def _record_failure(store: JobStore, job_id: str, fallback: JobMetadata, exc: Exception) -> JobMetadata:
    retryable = not _is_non_retryable_error(exc)
    error_message = str(exc)

    def update(metadata: JobMetadata) -> JobMetadata:
        metadata.last_error = error_message
        metadata.started_at = None
        metadata.heartbeat_at = None
        metadata.worker_id = None
        if retryable and metadata.attempts < metadata.max_attempts:
            metadata.status = "queued"
            metadata.stage = "queued"
            metadata.stage_message = "Queued for retry."
            metadata.error = None
        else:
            metadata.status = "failed"
            metadata.stage = "failed"
            metadata.stage_message = _failed_message(metadata)
            metadata.error = error_message
        return metadata

    return store.update_job(job_id, update) or fallback


def _is_non_retryable_error(exc: Exception) -> bool:
    return isinstance(exc, (ValueError, NotImplementedError, ValidationError)) or type(exc).__name__ == "UnidentifiedImageError"


def _cancelled_message(metadata: JobMetadata) -> str:
    return "Sprite-sheet creation cancelled." if metadata.job_type == "sprite_sheet" else "Restoration cancelled."


def _failed_message(metadata: JobMetadata) -> str:
    return "Sprite-sheet creation failed." if metadata.job_type == "sprite_sheet" else "Restoration failed."
