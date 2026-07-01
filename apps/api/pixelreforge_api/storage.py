from pathlib import Path
import json
import logging
import shutil
from uuid import uuid4

from fastapi import UploadFile
from pydantic import ValidationError

from .models import JobMetadata


logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[3]
RUNTIME_DIR = ROOT / "runtime" / "jobs"


def create_job(file: UploadFile) -> JobMetadata:
    job_id = uuid4().hex
    job_dir = RUNTIME_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=False)

    filename = Path(file.filename or "input").name
    input_path = job_dir / filename
    with input_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    metadata = JobMetadata(
        job_id=job_id,
        status="queued",
        input_filename=filename,
        input_path=str(input_path.relative_to(ROOT)),
    )
    write_metadata(metadata)
    logger.info(
        "Job created.",
        extra={
            "event": "job_created",
            "job_id": job_id,
            "status": metadata.status,
            "input_filename": filename,
            "content_type": file.content_type,
        },
    )
    return metadata


def get_job_dir(job_id: str) -> Path:
    return RUNTIME_DIR / job_id


def get_metadata_path(job_id: str) -> Path:
    return get_job_dir(job_id) / "metadata.json"


def read_metadata(job_id: str) -> JobMetadata | None:
    metadata_path = get_metadata_path(job_id)
    if not metadata_path.exists():
        return None
    try:
        return JobMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        logger.warning(
            "Job metadata is unreadable.",
            extra={"event": "job_metadata_unreadable", "job_id": job_id, "error_type": type(exc).__name__},
        )
        return None


def write_metadata(metadata: JobMetadata) -> None:
    metadata_path = get_metadata_path(metadata.job_id)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = metadata_path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(metadata.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(metadata_path)
