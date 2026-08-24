import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from .job_store import JobStore, create_job_store
from .logging_config import configure_logging
from .logging_context import reset_request_id, set_request_id
from .models import JobCreateResponse, JobListResponse, JobMetadata, JobParameters, JobPublicMetadata, PaletteCleanupMode, RestoreAlgorithm, ScaleMode, SheetExtractionMode, SpriteSheetInputMode, SpriteSheetPackingMode, SpriteSheetParameters, SpriteSheetSortMode
from .processing import output_file_path
from .sentry_config import configure_sentry
from .session import resolve_anonymous_session
from .settings import ApiSettings, load_settings
from .storage import delete_job_files, metadata_file_path_for_job, save_job_input, save_job_inputs


logger = logging.getLogger(__name__)


def create_app(settings: ApiSettings | None = None, job_store: JobStore | None = None) -> FastAPI:
    settings = settings or load_settings()
    if settings.is_production and not settings.session_secret:
        raise ValueError("PIXELREFORGE_SESSION_SECRET is required in production.")
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
    async def sprite_sheet_request_limit_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method == "POST" and request.url.path in {"/api/sprite-sheets", "/api/sprite-sheets/"}:
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    body_size = int(content_length)
                except ValueError:
                    body_size = 0
                if body_size > settings.sprite_sheet_max_request_bytes:
                    return _sprite_sheet_limit_response(request, settings)
        return await call_next(request)

    @api.middleware("http")
    async def anonymous_session_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method == "OPTIONS" or not request.url.path.startswith("/api/"):
            return await call_next(request)

        session = resolve_anonymous_session(
            request.cookies.get(settings.session_cookie_name),
            secret=settings.session_secret,
            max_age_seconds=settings.session_max_age_seconds,
        )
        request.state.anonymous_session_id = session.session_id
        response = await call_next(request)
        if session.should_set_cookie:
            response.set_cookie(
                key=settings.session_cookie_name,
                value=session.token,
                max_age=settings.session_max_age_seconds,
                httponly=True,
                secure=settings.is_production,
                samesite="lax",
                path="/",
            )
        return response

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
        request: Request,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> JobListResponse:
        owner_id = _session_id_from_request(request)
        jobs = [_public_job(metadata) for metadata in job_store.list_jobs(limit=limit, offset=offset, owner_id=owner_id)]
        return JobListResponse(jobs=jobs, limit=limit, offset=offset)

    @api.post("/api/jobs", response_model=JobCreateResponse, status_code=202)
    def create_processing_job(
        request: Request,
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
            owner_id=_session_id_from_request(request),
            job_type="restore",
            status="queued",
            progress_percent=5.0,
            stage="upload_accepted",
            stage_message="Upload accepted.",
            input_filename=input_filename,
            input_path=input_path,
            input_filenames=[input_filename],
            input_paths=[input_path],
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

    @api.post("/api/sprite-sheets", response_model=JobCreateResponse, status_code=202)
    def create_sprite_sheet_job(
        request: Request,
        files: list[UploadFile] = File(...),
        input_mode: SpriteSheetInputMode = Query(default="files"),
        packing_mode: SpriteSheetPackingMode = Query(default="compact"),
        trim_transparent: bool = Query(default=True),
        alpha_threshold: int = Query(default=0, ge=0, le=255),
        padding: int = Query(default=1, ge=0, le=64),
        border_padding: int = Query(default=0, ge=0, le=64),
        extrude: int = Query(default=0, ge=0, le=64),
        max_width: int = Query(default=2048, ge=1, le=8192),
        max_height: int = Query(default=2048, ge=1, le=8192),
        atlas_width: int | None = Query(default=None, ge=1, le=8192),
        atlas_height: int | None = Query(default=None, ge=1, le=8192),
        power_of_two: bool = Query(default=False),
        force_square: bool = Query(default=False),
        allow_rotation: bool = Query(default=False),
        sort_mode: SpriteSheetSortMode = Query(default="area"),
        grid_columns: int | None = Query(default=None, ge=1, le=512),
        background_color: str | None = Query(default=None),
        include_metadata: bool = Query(default=True),
        extraction_mode: SheetExtractionMode = Query(default="auto"),
        cell_width: int | None = Query(default=None, ge=1, le=8192),
        cell_height: int | None = Query(default=None, ge=1, le=8192),
        columns: int | None = Query(default=None, ge=1, le=512),
        rows: int | None = Query(default=None, ge=1, le=512),
        offset_x: int = Query(default=0, ge=0, le=8192),
        offset_y: int = Query(default=0, ge=0, le=8192),
        gap_x: int = Query(default=0, ge=0, le=8192),
        gap_y: int = Query(default=0, ge=0, le=8192),
    ) -> JobCreateResponse:
        params = _build_sprite_sheet_parameters(
            input_mode=input_mode,
            packing_mode=packing_mode,
            trim_transparent=trim_transparent,
            alpha_threshold=alpha_threshold,
            padding=padding,
            border_padding=border_padding,
            extrude=extrude,
            max_width=max_width,
            max_height=max_height,
            max_atlas_pixels=settings.sprite_sheet_max_atlas_pixels,
            atlas_width=atlas_width,
            atlas_height=atlas_height,
            power_of_two=power_of_two,
            force_square=force_square,
            allow_rotation=allow_rotation,
            sort_mode=sort_mode,
            grid_columns=grid_columns,
            background_color=background_color,
            include_metadata=include_metadata,
            extraction_mode=extraction_mode,
            cell_width=cell_width,
            cell_height=cell_height,
            columns=columns,
            rows=rows,
            offset_x=offset_x,
            offset_y=offset_y,
            gap_x=gap_x,
            gap_y=gap_y,
            max_frames=settings.sprite_sheet_max_frames,
        )
        _validate_sprite_sheet_uploads(files, params, settings)
        job_id = uuid4().hex
        try:
            saved_inputs = save_job_inputs(
                job_id,
                files,
                max_file_bytes=settings.sprite_sheet_max_file_bytes,
                max_total_bytes=settings.sprite_sheet_max_total_bytes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        input_filenames = [filename for filename, _ in saved_inputs]
        input_paths = [path for _, path in saved_inputs]
        now = datetime.now(UTC)
        metadata = JobMetadata(
            job_id=job_id,
            owner_id=_session_id_from_request(request),
            job_type="sprite_sheet",
            status="queued",
            progress_percent=5.0,
            stage="upload_accepted",
            stage_message="Sprite images accepted.",
            input_filename=input_filenames[0],
            input_path=input_paths[0],
            input_filenames=input_filenames,
            input_paths=input_paths,
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
            "Sprite-sheet job created.",
            extra={"event": "sprite_sheet_job_created", "job_id": metadata.job_id, "input_count": len(input_filenames)},
        )
        return JobCreateResponse(
            job_id=metadata.job_id,
            status=metadata.status,
            status_url=f"/api/sprite-sheets/{metadata.job_id}",
            download_url=f"/api/sprite-sheets/{metadata.job_id}/download",
        )

    @api.get("/api/jobs/{job_id}", response_model=JobPublicMetadata)
    def get_processing_job(job_id: str, request: Request) -> JobPublicMetadata:
        metadata = _owned_job_or_404(job_store, job_id, _session_id_from_request(request))
        return _public_job(metadata)

    @api.get("/api/sprite-sheets/{job_id}", response_model=JobPublicMetadata)
    def get_sprite_sheet_job(job_id: str, request: Request) -> JobPublicMetadata:
        metadata = _owned_sprite_sheet_job_or_404(job_store, job_id, _session_id_from_request(request))
        return _public_job(metadata)

    @api.get("/api/jobs/{job_id}/download")
    def download_processing_result(job_id: str, request: Request) -> FileResponse:
        metadata = _owned_job_or_404(job_store, job_id, _session_id_from_request(request))
        if metadata.status != "completed":
            raise HTTPException(status_code=409, detail="Job is not completed.")

        output_path = output_file_path(metadata)
        if output_path is None or not output_path.exists():
            raise HTTPException(status_code=404, detail="Output file not found.")
        filename = "pixelreforge-sprite-sheet.png" if metadata.job_type == "sprite_sheet" else "pixelreforge-result.png"
        return FileResponse(output_path, media_type="image/png", filename=filename)

    @api.get("/api/sprite-sheets/{job_id}/download")
    def download_sprite_sheet_result(job_id: str, request: Request) -> FileResponse:
        metadata = _owned_sprite_sheet_job_or_404(job_store, job_id, _session_id_from_request(request))
        if metadata.status != "completed":
            raise HTTPException(status_code=409, detail="Sprite-sheet job is not completed.")
        output_path = output_file_path(metadata)
        if output_path is None or not output_path.exists():
            raise HTTPException(status_code=404, detail="Output file not found.")
        return FileResponse(output_path, media_type="image/png", filename="pixelreforge-sprite-sheet.png")

    @api.get("/api/sprite-sheets/{job_id}/metadata")
    def download_sprite_sheet_metadata(job_id: str, request: Request) -> FileResponse:
        metadata = _owned_sprite_sheet_job_or_404(job_store, job_id, _session_id_from_request(request))
        if metadata.status != "completed":
            raise HTTPException(status_code=409, detail="Sprite-sheet job is not completed.")
        params = SpriteSheetParameters.model_validate(metadata.params)
        if not params.include_metadata:
            raise HTTPException(status_code=404, detail="Metadata export was not requested.")
        metadata_path = metadata_file_path_for_job(job_id)
        if not metadata_path.exists():
            raise HTTPException(status_code=404, detail="Metadata file not found.")
        return FileResponse(metadata_path, media_type="application/json", filename="pixelreforge-sprite-sheet.json")

    @api.post("/api/jobs/{job_id}/cancel", response_model=JobPublicMetadata)
    def cancel_processing_job(job_id: str, request: Request) -> JobPublicMetadata:
        owner_id = _session_id_from_request(request)
        metadata = _owned_job_or_404(job_store, job_id, owner_id)
        return _cancel_job(job_store, metadata, owner_id)

    @api.post("/api/sprite-sheets/{job_id}/cancel", response_model=JobPublicMetadata)
    def cancel_sprite_sheet_job(job_id: str, request: Request) -> JobPublicMetadata:
        owner_id = _session_id_from_request(request)
        metadata = _owned_sprite_sheet_job_or_404(job_store, job_id, owner_id)
        return _cancel_job(job_store, metadata, owner_id)

    return api


def _cancel_job(job_store: JobStore, metadata: JobMetadata, owner_id: str) -> JobPublicMetadata:
    if metadata.status in ("completed", "failed", "cancelled"):
        return _public_job(metadata)

    def mark_cancelled(current: JobMetadata) -> JobMetadata:
        if current.status not in ("completed", "failed", "cancelled"):
            current.cancel_requested = True
            current.status = "cancelled"
            current.stage = "cancelled"
            current.stage_message = "Sprite-sheet creation cancelled." if current.job_type == "sprite_sheet" else "Restoration cancelled."
            current.error = None
            current.started_at = None
            current.heartbeat_at = None
            current.worker_id = None
        return current

    updated_metadata = job_store.update_job(metadata.job_id, mark_cancelled)
    if updated_metadata is None or updated_metadata.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Job not found.")
    logger.info("Job cancelled.", extra={"event": "job_cancelled", "job_id": metadata.job_id, "status": updated_metadata.status})
    return _public_job(updated_metadata)


def _session_id_from_request(request: Request) -> str:
    session_id = getattr(request.state, "anonymous_session_id", None)
    if not isinstance(session_id, str) or not session_id:
        raise HTTPException(status_code=500, detail="Anonymous session is unavailable.")
    return session_id


def _owned_job_or_404(job_store: JobStore, job_id: str, owner_id: str) -> JobMetadata:
    metadata = job_store.get_job(job_id)
    if metadata is None or metadata.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Job not found.")
    return metadata


def _owned_sprite_sheet_job_or_404(job_store: JobStore, job_id: str, owner_id: str) -> JobMetadata:
    metadata = _owned_job_or_404(job_store, job_id, owner_id)
    if metadata.job_type != "sprite_sheet":
        raise HTTPException(status_code=404, detail="Sprite-sheet job not found.")
    return metadata


def _public_job(metadata: JobMetadata) -> JobPublicMetadata:
    return JobPublicMetadata.model_validate(metadata.model_dump())


def _validate_sprite_sheet_uploads(files: list[UploadFile], params: SpriteSheetParameters, settings: ApiSettings) -> None:
    if not files:
        raise HTTPException(status_code=422, detail="At least one sprite image is required.")
    if len(files) > settings.sprite_sheet_max_files:
        raise HTTPException(status_code=422, detail=f"A maximum of {settings.sprite_sheet_max_files} sprite images can be uploaded.")
    if params.input_mode == "sheet" and len(files) != 1:
        raise HTTPException(status_code=422, detail="Sheet mode requires exactly one image.")
    if params.atlas_width is not None and params.atlas_height is not None:
        if params.atlas_width * params.atlas_height > settings.sprite_sheet_max_atlas_pixels:
            raise HTTPException(status_code=422, detail="Fixed atlas dimensions exceed the atlas pixel limit.")
    total_bytes = 0
    total_pixels = 0
    for file in files:
        if file.content_type is not None and not file.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="Only PNG, JPEG, GIF, and WebP images are supported.")
        if file.size is not None:
            if file.size > settings.sprite_sheet_max_file_bytes:
                raise HTTPException(status_code=413, detail="An uploaded sprite exceeds the per-file size limit.")
            total_bytes += file.size
        total_pixels += _validate_sprite_image(file, settings)
    if total_bytes > settings.sprite_sheet_max_total_bytes:
        raise HTTPException(status_code=413, detail="Uploaded sprites exceed the total size limit.")
    if total_pixels > settings.sprite_sheet_max_total_pixels:
        raise HTTPException(status_code=413, detail="Uploaded sprites exceed the total pixel limit.")


def _validate_sprite_image(file: UploadFile, settings: ApiSettings) -> int:
    try:
        with Image.open(file.file) as image:
            if image.format not in {"PNG", "JPEG", "GIF", "WEBP"}:
                raise HTTPException(status_code=415, detail="Only PNG, JPEG, GIF, and WebP images are supported.")
            width, height = image.size
            pixels = width * height
            if pixels > settings.sprite_sheet_max_pixels:
                raise HTTPException(status_code=413, detail="An uploaded sprite exceeds the pixel limit.")
            image.verify()
            return pixels
    except HTTPException:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=422, detail="An uploaded file is not a valid image.") from exc
    finally:
        file.file.seek(0)


def _build_sprite_sheet_parameters(**values: object) -> SpriteSheetParameters:
    try:
        return SpriteSheetParameters.model_validate(values)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_context=False, include_input=False)) from exc


def _sprite_sheet_limit_response(request: Request, settings: ApiSettings) -> JSONResponse:
    response = JSONResponse(status_code=413, content={"detail": "Sprite-sheet upload exceeds the request size limit."})
    origin = request.headers.get("origin")
    if origin in settings.cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


app = create_app()
