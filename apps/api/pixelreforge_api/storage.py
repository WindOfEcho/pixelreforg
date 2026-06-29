from pathlib import Path
import json
import shutil
from uuid import uuid4

from fastapi import UploadFile

from .models import JobMetadata


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
    return metadata


def get_job_dir(job_id: str) -> Path:
    return RUNTIME_DIR / job_id


def get_metadata_path(job_id: str) -> Path:
    return get_job_dir(job_id) / "metadata.json"


def read_metadata(job_id: str) -> JobMetadata | None:
    metadata_path = get_metadata_path(job_id)
    if not metadata_path.exists():
        return None
    return JobMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))


def write_metadata(metadata: JobMetadata) -> None:
    metadata_path = get_metadata_path(metadata.job_id)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(metadata.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
