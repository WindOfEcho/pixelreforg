from dataclasses import replace
from io import BytesIO
import sqlite3

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from pixelreforge_api import create_app
from pixelreforge_api.job_store import SQLiteJobStore
from pixelreforge_api.settings import ApiSettings, load_settings
from pixelreforge_api.sprite_sheet_processing import SpriteSheetProcessingOutput
from pixelreforge_api.storage import get_job_dir
from pixelreforge_api.worker import JobWorker


@pytest.fixture
def api_settings(tmp_path) -> ApiSettings:
    return replace(
        load_settings(),
        database_url=f"sqlite:///{tmp_path / 'jobs.sqlite3'}",
        job_timeout_seconds=1,
        worker_heartbeat_interval_seconds=0.1,
        worker_id="sprite-sheet-test-worker",
    )


@pytest.fixture
def job_store(api_settings: ApiSettings) -> SQLiteJobStore:
    return SQLiteJobStore(api_settings.database_url)


@pytest.fixture
def worker(api_settings: ApiSettings, job_store: SQLiteJobStore) -> JobWorker:
    return JobWorker(job_store, api_settings)


@pytest.fixture
def client(api_settings: ApiSettings, job_store: SQLiteJobStore) -> TestClient:
    return TestClient(create_app(settings=api_settings, job_store=job_store))


def png_upload(
    name: str, size: tuple[int, int], color: tuple[int, int, int, int]
) -> tuple[str, tuple[str, BytesIO, str]]:
    image = Image.new("RGBA", size, color)
    payload = BytesIO()
    image.save(payload, format="PNG")
    payload.seek(0)
    return "files", (name, payload, "image/png")


def test_sprite_sheet_job_processes_multiple_images_and_exports_metadata(
    client: TestClient, worker: JobWorker
) -> None:
    response = client.post(
        "/api/sprite-sheets?packing_mode=grid&grid_columns=2&padding=1&include_metadata=true",
        files=[
            png_upload("hero.png", (2, 2), (255, 0, 0, 255)),
            png_upload("gem.png", (1, 3), (0, 0, 255, 255)),
        ],
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert worker.run_once() is True

    status_response = client.get(f"/api/sprite-sheets/{job_id}")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["job_type"] == "sprite_sheet"
    assert status["status"] == "completed"
    assert status["target_size"] == [5, 3]
    assert status["analysis"] == {
        "frame_count": 2,
        "input_mode": "files",
        "packing_mode": "grid",
        "metadata_available": True,
    }
    assert status["input_filenames"] == ["hero.png", "gem.png"]

    atlas_response = client.get(f"/api/sprite-sheets/{job_id}/download")
    assert atlas_response.status_code == 200
    assert atlas_response.headers["content-type"] == "image/png"
    assert atlas_response.content.startswith(b"\x89PNG")

    metadata_response = client.get(f"/api/sprite-sheets/{job_id}/metadata")
    assert metadata_response.status_code == 200
    metadata = metadata_response.json()
    assert tuple(metadata["frames"]) == ("hero", "gem")
    assert metadata["meta"]["size"] == {"w": 5, "h": 3}


def test_sprite_sheet_accepts_a_single_grid_extracted_sheet(
    client: TestClient, worker: JobWorker
) -> None:
    sheet = Image.new("RGBA", (6, 2), (0, 0, 0, 0))
    sheet.paste((255, 0, 0, 255), (0, 0, 2, 2))
    sheet.paste((0, 255, 0, 255), (4, 0, 6, 2))
    payload = BytesIO()
    sheet.save(payload, format="PNG")
    payload.seek(0)

    response = client.post(
        "/api/sprite-sheets?input_mode=sheet&extraction_mode=grid&cell_width=2&cell_height=2&columns=3&rows=1&packing_mode=grid&grid_columns=2",
        files=[("files", ("tiles.png", payload, "image/png"))],
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert worker.run_once() is True
    metadata = client.get(f"/api/sprite-sheets/{job_id}").json()
    assert metadata["status"] == "completed"
    assert metadata["analysis"]["frame_count"] == 2


def test_sprite_sheet_rejects_multiple_uploads_in_sheet_mode(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/sprite-sheets?input_mode=sheet",
        files=[
            png_upload("first.png", (1, 1), (255, 0, 0, 255)),
            png_upload("second.png", (1, 1), (0, 255, 0, 255)),
        ],
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Sheet mode requires exactly one image."


def test_sprite_sheet_rejects_invalid_image_payload(client: TestClient) -> None:
    response = client.post(
        "/api/sprite-sheets",
        files=[("files", ("not-an-image.png", BytesIO(b"not an image"), "image/png"))],
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "An uploaded file is not a valid image."


def test_sprite_sheet_hides_metadata_when_export_is_disabled(
    client: TestClient, worker: JobWorker
) -> None:
    response = client.post(
        "/api/sprite-sheets?include_metadata=false",
        files=[png_upload("sprite.png", (1, 1), (255, 0, 0, 255))],
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert worker.run_once() is True
    metadata_response = client.get(f"/api/sprite-sheets/{job_id}/metadata")
    assert metadata_response.status_code == 404


def test_sprite_sheet_rejects_a_batch_over_the_decoded_pixel_limit(
    api_settings: ApiSettings,
) -> None:
    settings = replace(api_settings, sprite_sheet_max_total_pixels=3)
    client = TestClient(
        create_app(settings=settings, job_store=SQLiteJobStore(settings.database_url))
    )

    response = client.post(
        "/api/sprite-sheets",
        files=[
            png_upload("first.png", (2, 1), (255, 0, 0, 255)),
            png_upload("second.png", (2, 1), (0, 255, 0, 255)),
        ],
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Uploaded sprites exceed the total pixel limit."


def test_sprite_sheet_rejects_fixed_atlas_over_pixel_limit(
    api_settings: ApiSettings,
) -> None:
    settings = replace(api_settings, sprite_sheet_max_atlas_pixels=4)
    client = TestClient(
        create_app(settings=settings, job_store=SQLiteJobStore(settings.database_url))
    )

    response = client.post(
        "/api/sprite-sheets?atlas_width=3&atlas_height=2",
        files=[png_upload("sprite.png", (1, 1), (255, 0, 0, 255))],
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "Fixed atlas dimensions exceed the atlas pixel limit."
    )


def test_sprite_sheet_rejects_request_before_multipart_parsing(
    api_settings: ApiSettings,
) -> None:
    settings = replace(api_settings, sprite_sheet_max_request_bytes=1)
    client = TestClient(
        create_app(settings=settings, job_store=SQLiteJobStore(settings.database_url))
    )

    response = client.post(
        "/api/sprite-sheets",
        files=[png_upload("sprite.png", (1, 1), (255, 0, 0, 255))],
    )

    assert response.status_code == 413
    assert (
        response.json()["detail"]
        == "Sprite-sheet upload exceeds the request size limit."
    )


def test_sprite_sheet_request_limit_covers_trailing_slash_and_preserves_cors(
    api_settings: ApiSettings,
) -> None:
    settings = replace(api_settings, sprite_sheet_max_request_bytes=1)
    client = TestClient(
        create_app(settings=settings, job_store=SQLiteJobStore(settings.database_url))
    )

    response = client.post(
        "/api/sprite-sheets/",
        files=[png_upload("sprite.png", (1, 1), (255, 0, 0, 255))],
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_sprite_sheet_grid_respects_configured_frame_limit(
    api_settings: ApiSettings,
) -> None:
    settings = replace(api_settings, sprite_sheet_max_frames=4)
    client = TestClient(
        create_app(settings=settings, job_store=SQLiteJobStore(settings.database_url))
    )

    response = client.post(
        "/api/sprite-sheets?input_mode=sheet&extraction_mode=grid&cell_width=1&cell_height=1&columns=3&rows=2",
        files=[png_upload("sheet.png", (3, 2), (255, 0, 0, 255))],
    )

    assert response.status_code == 422


def test_cancelled_sprite_sheet_job_cannot_be_completed_by_worker_race(
    client: TestClient,
    worker: JobWorker,
    job_store: SQLiteJobStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = client.post(
        "/api/sprite-sheets",
        files=[png_upload("sprite.png", (1, 1), (255, 0, 0, 255))],
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    def fake_processing(metadata, *, progress, cancel):  # type: ignore[no-untyped-def]
        output_path = get_job_dir(metadata.job_id) / "output.png"
        output_path.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        return SpriteSheetProcessingOutput(
            output_path=output_path,
            metadata_path=None,
            atlas_size=(1, 1),
            frame_count=1,
            warnings=(),
        )

    original_update = job_store.update_job

    def update_with_cancellation(job_id: str, update):  # type: ignore[no-untyped-def]
        if update.__name__ == "complete":

            def cancel_before_complete(metadata):  # type: ignore[no-untyped-def]
                metadata.status = "cancelled"
                metadata.cancel_requested = True
                return metadata

            original_update(job_id, cancel_before_complete)
        return original_update(job_id, update)

    monkeypatch.setattr(
        "pixelreforge_api.processing.process_sprite_sheet_job", fake_processing
    )
    monkeypatch.setattr(job_store, "update_job", update_with_cancellation)

    assert worker.run_once() is True
    metadata = job_store.get_job(job_id)
    assert metadata is not None
    assert metadata.status == "cancelled"
    assert metadata.output_path is None


def test_job_store_migrates_legacy_restore_rows(tmp_path) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE jobs (
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
            );
            """
        )
        connection.execute(
            """
            INSERT INTO jobs (
                job_id, status, progress_percent, input_filename, input_path,
                warnings, attempts, max_attempts, cancel_requested, params
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-job",
                "queued",
                0.0,
                "legacy.png",
                "runtime/jobs/legacy-job/input.png",
                "[]",
                0,
                3,
                0,
                "{}",
            ),
        )

    store = SQLiteJobStore(f"sqlite:///{database_path}")

    migrated = store.get_job("legacy-job")
    assert migrated is not None
    assert migrated.job_type == "restore"
    assert migrated.input_filenames == []
    assert migrated.input_paths == []
    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
    assert {"job_type", "input_filenames", "input_paths"} <= columns
