from __future__ import annotations

from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime, timedelta
import json
import logging
from pathlib import Path
import sqlite3
from typing import Protocol

from .models import JobMetadata
from .settings import ApiSettings


logger = logging.getLogger(__name__)
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
JSON_FIELDS = {
    "source_size",
    "target_size",
    "original_size_override",
    "analysis",
    "palette",
    "reconstruction",
    "warnings",
    "params",
}
COLUMNS = [
    "job_id",
    "owner_id",
    "status",
    "progress_percent",
    "stage",
    "stage_message",
    "input_filename",
    "input_path",
    "output_path",
    "algorithm_requested",
    "algorithm_used",
    "algorithm_version",
    "source_size",
    "target_size",
    "original_size_override",
    "scale_x",
    "scale_y",
    "scale_method",
    "confidence",
    "palette_cleanup",
    "analysis",
    "palette",
    "reconstruction",
    "warnings",
    "error",
    "attempts",
    "max_attempts",
    "last_error",
    "started_at",
    "heartbeat_at",
    "created_at",
    "updated_at",
    "expires_at",
    "cancel_requested",
    "worker_id",
    "params",
]


class JobStore(Protocol):
    def create_job(self, metadata: JobMetadata) -> JobMetadata: ...

    def get_job(self, job_id: str) -> JobMetadata | None: ...

    def list_jobs(self, *, limit: int, offset: int, owner_id: str | None = None) -> list[JobMetadata]: ...

    def update_job(self, job_id: str, update: Callable[[JobMetadata], JobMetadata]) -> JobMetadata | None: ...

    def claim_next_queued_job(self, *, worker_id: str) -> JobMetadata | None: ...

    def recover_interrupted_jobs(self, *, worker_id: str) -> int: ...

    def requeue_stale_jobs(self, *, timeout_seconds: int) -> int: ...

    def find_expired_terminal_jobs(self, *, limit: int) -> list[JobMetadata]: ...

    def delete_job(self, job_id: str) -> JobMetadata | None: ...


class SQLiteJobStore:
    def __init__(self, database_url: str) -> None:
        self.database_path = _sqlite_path(database_url)
        if self.database_path != Path(":memory:"):
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def create_job(self, metadata: JobMetadata) -> JobMetadata:
        now = _utcnow()
        metadata = metadata.model_copy(
            update={
                "created_at": metadata.created_at or now,
                "updated_at": metadata.updated_at or now,
            }
        )
        with closing(self._connect()) as connection:
            _replace_metadata(connection, metadata)
            connection.commit()
        return metadata

    def get_job(self, job_id: str) -> JobMetadata | None:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_to_metadata(row) if row is not None else None

    def list_jobs(self, *, limit: int, offset: int, owner_id: str | None = None) -> list[JobMetadata]:
        limit = max(1, min(100, limit))
        offset = max(0, offset)
        with closing(self._connect()) as connection:
            if owner_id is None:
                rows = connection.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC, job_id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM jobs WHERE owner_id = ? ORDER BY created_at DESC, job_id DESC LIMIT ? OFFSET ?",
                    (owner_id, limit, offset),
                ).fetchall()
        return [_row_to_metadata(row) for row in rows]

    def update_job(self, job_id: str, update: Callable[[JobMetadata], JobMetadata]) -> JobMetadata | None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                connection.rollback()
                return None
            metadata = update(_row_to_metadata(row))
            metadata.updated_at = _utcnow()
            _replace_metadata(connection, metadata)
            connection.commit()
            return metadata

    def claim_next_queued_job(self, *, worker_id: str) -> JobMetadata | None:
        now = _utcnow()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'queued' AND attempts < max_attempts
                ORDER BY created_at ASC, job_id ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                connection.rollback()
                return None

            metadata = _row_to_metadata(row)
            metadata.status = "processing"
            metadata.attempts += 1
            metadata.started_at = now
            metadata.heartbeat_at = now
            metadata.updated_at = now
            metadata.worker_id = worker_id
            metadata.stage = "processing"
            metadata.stage_message = "Processing image..."
            _replace_metadata(connection, metadata)
            connection.commit()
            return metadata

    def recover_interrupted_jobs(self, *, worker_id: str) -> int:
        now = _utcnow()
        recovered = 0
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'processing' AND (worker_id IS NULL OR worker_id = ?)
                """,
                (worker_id,),
            ).fetchall()
            for row in rows:
                metadata = _reset_processing_job(_row_to_metadata(row), now, "Worker was interrupted.")
                _replace_metadata(connection, metadata)
                recovered += 1
            connection.commit()
        return recovered

    def requeue_stale_jobs(self, *, timeout_seconds: int) -> int:
        now = _utcnow()
        threshold = now - timedelta(seconds=timeout_seconds)
        recovered = 0
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute("SELECT * FROM jobs WHERE status = 'processing'").fetchall()
            for row in rows:
                metadata = _row_to_metadata(row)
                heartbeat = metadata.heartbeat_at or metadata.started_at
                started = metadata.started_at or metadata.heartbeat_at
                if heartbeat is not None and heartbeat > threshold and started is not None and started > threshold:
                    continue
                metadata = _reset_processing_job(metadata, now, "Processing timed out.")
                _replace_metadata(connection, metadata)
                recovered += 1
            connection.commit()
        return recovered

    def find_expired_terminal_jobs(self, *, limit: int) -> list[JobMetadata]:
        now = _utcnow()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM jobs
                WHERE status IN ('completed', 'failed', 'cancelled') AND expires_at IS NOT NULL
                ORDER BY expires_at ASC
                LIMIT ?
                """,
                (max(1, limit),),
            ).fetchall()
        expired = []
        for row in rows:
            metadata = _row_to_metadata(row)
            if metadata.expires_at is not None and metadata.expires_at <= now:
                expired.append(metadata)
        return expired

    def delete_job(self, job_id: str) -> JobMetadata | None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                connection.rollback()
                return None
            metadata = _row_to_metadata(row)
            connection.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            connection.commit()
            return metadata

    def _init_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    owner_id TEXT,
                    status TEXT NOT NULL,
                    progress_percent REAL NOT NULL,
                    stage TEXT,
                    stage_message TEXT,
                    input_filename TEXT NOT NULL,
                    input_path TEXT NOT NULL,
                    output_path TEXT,
                    algorithm_requested TEXT,
                    algorithm_used TEXT,
                    algorithm_version TEXT,
                    source_size TEXT,
                    target_size TEXT,
                    original_size_override TEXT,
                    scale_x REAL,
                    scale_y REAL,
                    scale_method TEXT,
                    confidence REAL,
                    palette_cleanup TEXT,
                    analysis TEXT,
                    palette TEXT,
                    reconstruction TEXT,
                    warnings TEXT NOT NULL,
                    error TEXT,
                    attempts INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    last_error TEXT,
                    started_at TEXT,
                    heartbeat_at TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    expires_at TEXT,
                    cancel_requested INTEGER NOT NULL,
                    worker_id TEXT,
                    params TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_owner_created ON jobs(owner_id, created_at)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_jobs_expires_at ON jobs(expires_at)")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        if self.database_path != Path(":memory:"):
            connection.execute("PRAGMA journal_mode = WAL")
        return connection


def create_job_store(settings: ApiSettings) -> JobStore:
    if settings.database_url.startswith("sqlite:///") or not "://" in settings.database_url:
        return SQLiteJobStore(settings.database_url)
    raise ValueError(f"Unsupported job database URL: {settings.database_url}")


def _sqlite_path(database_url: str) -> Path:
    if database_url.startswith("sqlite:///"):
        value = database_url.removeprefix("sqlite:///")
    else:
        value = database_url
    if value == ":memory:":
        return Path(":memory:")
    return Path(value).expanduser().resolve()


def _replace_metadata(connection: sqlite3.Connection, metadata: JobMetadata) -> None:
    row = _metadata_to_row(metadata)
    placeholders = ", ".join("?" for _ in COLUMNS)
    columns = ", ".join(COLUMNS)
    connection.execute(
        f"INSERT OR REPLACE INTO jobs ({columns}) VALUES ({placeholders})",
        tuple(row[column] for column in COLUMNS),
    )


def _metadata_to_row(metadata: JobMetadata) -> dict[str, object | None]:
    data = metadata.model_dump(mode="json")
    for field in JSON_FIELDS:
        value = data[field]
        data[field] = json.dumps(value, ensure_ascii=False) if value is not None else None
    data["cancel_requested"] = 1 if metadata.cancel_requested else 0
    return {column: data.get(column) for column in COLUMNS}


def _row_to_metadata(row: sqlite3.Row) -> JobMetadata:
    data = dict(row)
    for field in JSON_FIELDS:
        value = data[field]
        data[field] = json.loads(value) if value else ([] if field == "warnings" else {} if field == "params" else None)
    data["cancel_requested"] = bool(data["cancel_requested"])
    return JobMetadata.model_validate(data)


def _reset_processing_job(metadata: JobMetadata, now: datetime, reason: str) -> JobMetadata:
    if metadata.cancel_requested or metadata.status == "cancelled":
        metadata.status = "cancelled"
        metadata.stage = "cancelled"
        metadata.stage_message = "Restoration cancelled."
        metadata.error = None
    elif metadata.attempts >= metadata.max_attempts:
        metadata.status = "failed"
        metadata.stage = "failed"
        metadata.stage_message = "Restoration failed."
        metadata.error = reason
    else:
        metadata.status = "queued"
        metadata.stage = "queued"
        metadata.stage_message = "Queued for retry."
        metadata.error = None
    metadata.last_error = reason
    metadata.started_at = None
    metadata.heartbeat_at = None
    metadata.worker_id = None
    metadata.updated_at = now
    return metadata


def _utcnow() -> datetime:
    return datetime.now(UTC)
