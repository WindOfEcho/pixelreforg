from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .models import JobCreateResponse, JobMetadata, PaletteCleanupMode, RestoreAlgorithm, ScaleMode
from .processing import output_file_path, process_job
from .storage import create_job, read_metadata, write_metadata


def create_app() -> FastAPI:
    api = FastAPI(title="PixelReForge API", version="0.1.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/api/jobs", response_model=JobCreateResponse, status_code=202)
    def create_processing_job(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        algorithm: RestoreAlgorithm = Query(default="auto"),
        scale_mode: ScaleMode = Query(default="manual"),
        scale: int | None = Query(default=4, ge=2, le=16),
        min_scale: int = Query(default=2, ge=1, le=64),
        max_scale: int = Query(default=16, ge=1, le=64),
        original_width: int | None = Query(default=None, ge=1),
        original_height: int | None = Query(default=None, ge=1),
        palette_cleanup: PaletteCleanupMode = Query(default="off"),
        palette_merge_distance: float | None = Query(default=None, ge=0.0, le=128.0),
        palette_target_colors: int | None = Query(default=None, ge=1, le=256),
        noisy_color_bucket_size: int = Query(default=16, ge=2, le=64),
        confidence_threshold: float = Query(default=0.45, ge=0.0, le=1.0),
    ) -> JobCreateResponse:
        if file.content_type is not None and not file.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="Only image uploads are supported.")
        if min_scale > max_scale:
            raise HTTPException(status_code=422, detail="min_scale must be less than or equal to max_scale.")
        if scale_mode == "manual" and scale is None:
            raise HTTPException(status_code=422, detail="Manual scale mode requires scale.")

        metadata = create_job(file)
        background_tasks.add_task(
            process_job,
            metadata.job_id,
            algorithm,
            scale_mode,
            scale,
            min_scale,
            max_scale,
            original_width,
            original_height,
            palette_cleanup,
            palette_merge_distance,
            palette_target_colors,
            noisy_color_bucket_size,
            confidence_threshold,
        )
        return JobCreateResponse(
            job_id=metadata.job_id,
            status=metadata.status,
            status_url=f"/api/jobs/{metadata.job_id}",
            download_url=f"/api/jobs/{metadata.job_id}/download",
        )

    @api.get("/api/jobs/{job_id}", response_model=JobMetadata)
    def get_processing_job(job_id: str) -> JobMetadata:
        metadata = read_metadata(job_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return metadata

    @api.get("/api/jobs/{job_id}/download")
    def download_processing_result(job_id: str) -> FileResponse:
        metadata = read_metadata(job_id)
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
        metadata = read_metadata(job_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        if metadata.status in ("completed", "failed", "cancelled"):
            return metadata

        metadata.status = "cancelled"
        metadata.error = None
        write_metadata(metadata)
        return metadata

    return api


app = create_app()
