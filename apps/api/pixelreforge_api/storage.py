from pathlib import Path
import logging
import os
import shutil

from fastapi import UploadFile

from .models import JobMetadata


logger = logging.getLogger(__name__)
ROOT = Path(os.getenv("PIXELREFORGE_ROOT", Path.cwd())).resolve()
RUNTIME_DIR = ROOT / "runtime" / "jobs"


def save_job_input(job_id: str, file: UploadFile) -> tuple[str, str]:
    job_dir = get_job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=False)

    filename = Path(file.filename or "input").name or "input"
    input_path = job_dir / filename
    with input_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    logger.info(
        "Job input saved.",
        extra={
            "event": "job_input_saved",
            "job_id": job_id,
            "input_filename": filename,
            "content_type": file.content_type,
        },
    )
    return filename, str(input_path.relative_to(ROOT))


def get_job_dir(job_id: str) -> Path:
    return RUNTIME_DIR / job_id


def output_file_path(metadata: JobMetadata) -> Path | None:
    if metadata.output_path is None:
        return None
    return ROOT / metadata.output_path


def output_file_path_for_job(job_id: str) -> Path:
    return get_job_dir(job_id) / "output.png"


def delete_job_files(job_id: str) -> None:
    shutil.rmtree(get_job_dir(job_id), ignore_errors=True)
