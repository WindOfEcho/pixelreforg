import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .job_store import JobStore, create_job_store
from .logging_config import configure_logging
from .logging_context import reset_request_id, set_request_id
from .models import JobCreateResponse, JobListResponse, JobMetadata, JobParameters, PaletteCleanupMode, RestoreAlgorithm, ScaleMode
from .processing import output_file_path
from .sentry_config import configure_sentry
from .settings import ApiSettings, load_settings
from .storage import delete_job_files, save_job_input


logger = logging.getLogger(__name__)


def create_app(settings: ApiSettings | None = None, job_store: JobStore | None = None) -> FastAPI:
    settings = settings or load_settings()
    job_store = job_store or create_job_store(settings)
    configure_logging(settings)
    configure_sentry(settings)
    api = FastAPI(title="PixelReForge API", version="0.1.0")
    api.state.job_store = job_store
    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info(
        "API logging configured.",
        extra={
            "event": "api_logging_configured",
            "env": settings.env,
            "debug": settings.debug,
            "log_level": settings.log_level,
            "log_format": settings.log_format,
        },
    )

    @api.middleware("http")
    async def request_logging_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        token = set_request_id(request_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "Request failed.",
                extra={
                    "event": "request_failed",
                    "method": request.method,
                    "path": request.url.path,
                    "request_id": request_id,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            if settings.log_successful_requests or status_code >= 400:
                level = logging.WARNING if status_code >= 400 else logging.INFO
                logger.log(
                    level,
                    "Request finished.",
                    extra={
                        "event": "request_finished",
                        "method": request.method,
                        "path": request.url.path,
                        "request_id": request_id,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    },
                )
            reset_request_id(token)

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/api/jobs", response_model=JobListResponse)
    def list_processing_jobs(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> JobListResponse:
        return JobListResponse(jobs=job_store.list_jobs(limit=limit, offset=offset), limit=limit, offset=offset)

    @api.post("/api/jobs", response_model=JobCreateResponse, status_code=202)
    def create_processing_job(
        file: UploadFile = File(...),
        algorithm: RestoreAlgorithm = Query(default="auto"),
        scale_mode: ScaleMode = Query(default="manual"),
        scale: float | None = Query(default=4, ge=1.0, le=64.0),
        min_scale: int = Query(default=2, ge=1, le=64),
        max_scale: int = Query(default=16, ge=1, le=64),
        original_width: int | None = Query(default=None, ge=1),
        original_height: int | None = Query(default=None, ge=1),
        palette_cleanup: PaletteCleanupMode = Query(default="off"),
        palette_merge_distance: float | None = Query(default=None, ge=0.0, le=128.0),
        palette_target_colors: int | None = Query(default=None, ge=1, le=256),
        noisy_color_bucket_size: int = Query(default=16, ge=2, le=64),
        confidence_threshold: float = Query(default=0.45, ge=0.0, le=1.0),
        fractional_scale_step: float = Query(default=0.25, ge=0.05, le=1.0),
    ) -> JobCreateResponse:
        if file.content_type is not None and not file.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="Only image uploads are supported.")
        if min_scale > max_scale:
            raise HTTPException(status_code=422, detail="min_scale must be less than or equal to max_scale.")
        if scale_mode == "manual" and scale is None:
            raise HTTPException(status_code=422, detail="Manual scale mode requires scale.")

        params = JobParameters(
            algorithm=algorithm,
            scale_mode=scale_mode,
            scale=scale,
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
        job_id = uuid4().hex
        input_filename, input_path = save_job_input(job_id, file)
        now = datetime.now(UTC)
        metadata = JobMetadata(
            job_id=job_id,
            status="queued",
            progress_percent=5.0,
            stage="upload_accepted",
            stage_message="Upload accepted.",
            input_filename=input_filename,
            input_path=input_path,
            algorithm_requested=algorithm,
            palette_cleanup=palette_cleanup,
            attempts=0,
            max_attempts=settings.job_max_attempts,
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(seconds=settings.job_ttl_seconds),
            params=params.model_dump(mode="json"),
        )
        try:
            metadata = job_store.create_job(metadata)
        except Exception:
            delete_job_files(job_id)
            raise
        logger.info(
            "Job created.",
            extra={"event": "job_created", "job_id": metadata.job_id, "status": metadata.status, "input_filename": input_filename},
        )
        return JobCreateResponse(
            job_id=metadata.job_id,
            status=metadata.status,
            status_url=f"/api/jobs/{metadata.job_id}",
            download_url=f"/api/jobs/{metadata.job_id}/download",
        )

    @api.get("/api/jobs/{job_id}", response_model=JobMetadata)
    def get_processing_job(job_id: str) -> JobMetadata:
        metadata = job_store.get_job(job_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return metadata

    @api.get("/api/jobs/{job_id}/download")
    def download_processing_result(job_id: str) -> FileResponse:
        metadata = job_store.get_job(job_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        if metadata.status != "completed":
            raise HTTPException(status_code=409, detail="Job is not completed.")

        output_path = output_file_path(metadata)
        if output_path is None or not output_path.exists():
            raise HTTPException(status_code=404, detail="Output file not found.")
        return FileResponse(output_path, media_type="image/png", filename="pixelreforge-result.png")

    @api.post("/api/jobs/{job_id}/cancel", response_model=JobMetadata)
    def cancel_processing_job(job_id: str) -> JobMetadata:
        metadata = job_store.get_job(job_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        if metadata.status in ("completed", "failed", "cancelled"):
            return metadata

        def mark_cancelled(current: JobMetadata) -> JobMetadata:
            if current.status not in ("completed", "failed", "cancelled"):
                current.cancel_requested = True
                current.status = "cancelled"
                current.stage = "cancelled"
                current.stage_message = "Restoration cancelled."
                current.error = None
                current.started_at = None
                current.heartbeat_at = None
                current.worker_id = None
            return current

        metadata = job_store.update_job(job_id, mark_cancelled)
        if metadata is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        logger.info("Job cancelled.", extra={"event": "job_cancelled", "job_id": job_id, "status": metadata.status})
        return metadata

    return api


app = create_app()
