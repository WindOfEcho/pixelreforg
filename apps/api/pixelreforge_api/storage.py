from collections.abc import Sequence
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


def save_job_inputs(
    job_id: str,
    files: Sequence[UploadFile],
    *,
    max_file_bytes: int,
    max_total_bytes: int,
) -> list[tuple[str, str]]:
    """Persist a bounded batch of uploads under a single job directory."""

    job_dir = get_job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=False)
    saved: list[tuple[str, str]] = []
    total_bytes = 0
    try:
        for index, file in enumerate(files, start=1):
            original_name = (
                Path(file.filename or f"sprite-{index:04d}").name
                or f"sprite-{index:04d}"
            )
            suffix = Path(original_name).suffix.lower()
            input_path = job_dir / f"input-{index:04d}{suffix}"
            written_bytes = 0
            with input_path.open("wb") as output:
                while chunk := file.file.read(1024 * 1024):
                    written_bytes += len(chunk)
                    total_bytes += len(chunk)
                    if written_bytes > max_file_bytes:
                        raise ValueError(
                            "An uploaded sprite exceeds the per-file size limit."
                        )
                    if total_bytes > max_total_bytes:
                        raise ValueError(
                            "Uploaded sprites exceed the total size limit."
                        )
                    output.write(chunk)
            saved.append((original_name, str(input_path.relative_to(ROOT))))
    except Exception:
        delete_job_files(job_id)
        raise

    logger.info(
        "Job inputs saved.",
        extra={
            "event": "job_inputs_saved",
            "job_id": job_id,
            "input_count": len(saved),
            "total_bytes": total_bytes,
        },
    )
    return saved


def get_job_dir(job_id: str) -> Path:
    return RUNTIME_DIR / job_id


def output_file_path(metadata: JobMetadata) -> Path | None:
    if metadata.output_path is None:
        return None
    return ROOT / metadata.output_path


def output_file_path_for_job(job_id: str) -> Path:
    return get_job_dir(job_id) / "output.png"


def metadata_file_path_for_job(job_id: str) -> Path:
    return get_job_dir(job_id) / "metadata.json"


def delete_job_files(job_id: str) -> None:
    shutil.rmtree(get_job_dir(job_id), ignore_errors=True)
