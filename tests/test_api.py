import json
import sys
import types
from dataclasses import replace
from datetime import UTC, datetime

from fastapi.testclient import TestClient
import pytest

from pixelreforge_api import create_app
from pixelreforge_api.job_store import SQLiteJobStore
from pixelreforge_api.sentry_config import configure_sentry
from pixelreforge_api.settings import ApiSettings, load_settings
from pixelreforge_api.models import JobMetadata
from pixelreforge_api.storage import ROOT, get_job_dir
from pixelreforge_api.worker import JobWorker


@pytest.fixture
def api_settings(tmp_path) -> ApiSettings:
    return replace(
        load_settings(),
        database_url=f"sqlite:///{tmp_path / 'jobs.sqlite3'}",
        job_timeout_seconds=1,
        worker_heartbeat_interval_seconds=0.1,
        worker_id="test-worker",
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


def run_worker_until_idle(worker: JobWorker, max_runs: int = 10) -> int:
    runs = 0
    while runs < max_runs and worker.run_once():
        runs += 1
    return runs


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "x-request-id" in response.headers


def test_request_id_header_is_preserved(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-id"


def test_production_request_logging_records_successful_requests(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("PIXELREFORGE_ENV", "production")
    monkeypatch.setenv("PIXELREFORGE_LOG_FORMAT", "json")
    monkeypatch.setenv("PIXELREFORGE_LOG_LEVEL", "INFO")
    production_app = create_app()
    production_client = TestClient(production_app)

    response = production_client.get("/health", headers={"X-Request-ID": "prod-request-id"})

    assert response.status_code == 200
    log_lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    finished = [record for record in log_lines if record["event"] == "request_finished"]
    assert len(finished) == 1
    assert finished[0]["request_id"] == "prod-request-id"
    assert finished[0]["status_code"] == 200


def test_settings_read_runtime_mode_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PIXELREFORGE_ENV", "production")
    monkeypatch.setenv("PIXELREFORGE_DEBUG", "true")
    monkeypatch.setenv("PIXELREFORGE_LOG_FORMAT", "json")
    monkeypatch.setenv("PIXELREFORGE_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("PIXELREFORGE_SENTRY_DSN", "https://public@example.invalid/1")
    monkeypatch.setenv("PIXELREFORGE_SENTRY_TRACES_SAMPLE_RATE", "0.25")
    monkeypatch.setenv("PIXELREFORGE_CORS_ORIGINS", "https://example.com")

    settings = load_settings()

    assert settings.env == "production"
    assert settings.debug is True
    assert settings.log_level == "ERROR"
    assert settings.log_format == "json"
    assert settings.sentry_dsn == "https://public@example.invalid/1"
    assert settings.sentry_traces_sample_rate == 0.25
    assert settings.cors_origins == ("https://example.com",)


def test_sentry_is_disabled_without_dsn(caplog: pytest.LogCaptureFixture) -> None:
    settings = ApiSettings(
        env="development",
        debug=True,
        log_level="INFO",
        log_format="plain",
        sentry_dsn=None,
        sentry_traces_sample_rate=0.0,
    )
    caplog.set_level("INFO", logger="pixelreforge_api.sentry_config")

    configure_sentry(settings)

    assert any(record.event == "sentry_disabled" for record in caplog.records)


def test_sentry_is_configured_with_dsn(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    init_call: dict = {}
    sentry_module = types.ModuleType("sentry_sdk")

    def fake_init(**kwargs):  # type: ignore[no-untyped-def]
        init_call.update(kwargs)

    class FakeFastApiIntegration:
        pass

    class FakeLoggingIntegration:
        def __init__(self, level: int, event_level: int) -> None:
            self.level = level
            self.event_level = event_level

    sentry_module.init = fake_init  # type: ignore[attr-defined]
    integrations_module = types.ModuleType("sentry_sdk.integrations")
    fastapi_module = types.ModuleType("sentry_sdk.integrations.fastapi")
    fastapi_module.FastApiIntegration = FakeFastApiIntegration  # type: ignore[attr-defined]
    logging_module = types.ModuleType("sentry_sdk.integrations.logging")
    logging_module.LoggingIntegration = FakeLoggingIntegration  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentry_sdk", sentry_module)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations", integrations_module)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.fastapi", fastapi_module)
    monkeypatch.setitem(sys.modules, "sentry_sdk.integrations.logging", logging_module)
    settings = ApiSettings(
        env="production",
        debug=False,
        log_level="INFO",
        log_format="json",
        sentry_dsn="https://public@example.invalid/1",
        sentry_traces_sample_rate=0.5,
    )
    caplog.set_level("INFO", logger="pixelreforge_api.sentry_config")

    configure_sentry(settings)

    assert init_call["dsn"] == "https://public@example.invalid/1"
    assert init_call["environment"] == "production"
    assert init_call["traces_sample_rate"] == 0.5
    assert init_call["send_default_pii"] is False
    assert any(record.event == "sentry_configured" for record in caplog.records)


def test_create_job_processes_fixture_and_downloads_result(client: TestClient, worker: JobWorker) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x4-90.jpg"

    with fixture_path.open("rb") as image_file:
        create_response = client.post(
            "/api/jobs?scale=4",
            files={"file": ("test-jpegs-x4-90.jpg", image_file, "image/jpeg")},
        )

    assert create_response.status_code == 202
    create_payload = create_response.json()
    job_id = create_payload["job_id"]
    assert create_payload["status"] == "queued"

    assert worker.run_once() is True

    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.status_code == 200
    metadata = status_response.json()
    assert metadata["status"] == "completed"
    assert metadata["progress_percent"] == 100
    assert metadata["stage"] == "completed"
    assert metadata["stage_message"] == "Restoration complete."
    assert metadata["source_size"] == [128, 128]
    assert metadata["target_size"] == [32, 32]
    assert metadata["scale_x"] == 4
    assert metadata["scale_y"] == 4
    assert metadata["algorithm_requested"] == "auto"
    assert metadata["algorithm_used"] == "noisy-pixel-v1"
    assert metadata["palette_cleanup"] == "off"
    assert metadata["analysis"] is not None
    assert "recommended_algorithm" in metadata["analysis"]

    download_response = client.get(f"/api/jobs/{job_id}/download")
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "image/png"
    assert download_response.content.startswith(b"\x89PNG")


def test_auto_algorithm_records_recommendation_and_fallback(client: TestClient, worker: JobWorker) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x4-60.jpg"

    with fixture_path.open("rb") as image_file:
        create_response = client.post(
            "/api/jobs?algorithm=auto&scale_mode=auto&min_scale=2&max_scale=16&palette_cleanup=light",
            files={"file": ("test-jpegs-x4-60.jpg", image_file, "image/jpeg")},
        )

    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]
    assert worker.run_once() is True

    metadata = client.get(f"/api/jobs/{job_id}").json()
    assert metadata["algorithm_requested"] == "auto"
    assert metadata["algorithm_used"] == "noisy-pixel-v1"
    assert metadata["reconstruction"]["resize_method"] == "dominant-color-cluster"
    assert metadata["palette_cleanup"] == "light"
    assert metadata["palette"]["cleanup_applied"] is True
    assert "color_count_after" in metadata["palette"]
    assert metadata["analysis"]["recommended_algorithm"] == "noisy-pixel-v1"


def test_explicit_noisy_pixel_algorithm_processes_fixture(client: TestClient, worker: JobWorker) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x10-60.jpg"

    with fixture_path.open("rb") as image_file:
        create_response = client.post(
            "/api/jobs?algorithm=noisy-pixel-v1&scale_mode=auto&min_scale=2&max_scale=16&palette_cleanup=medium",
            files={"file": ("test-jpegs-x10-60.jpg", image_file, "image/jpeg")},
        )

    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]
    assert worker.run_once() is True

    metadata = client.get(f"/api/jobs/{job_id}").json()
    assert metadata["status"] == "completed"
    assert metadata["algorithm_used"] == "noisy-pixel-v1"
    assert metadata["target_size"] == [32, 32]
    assert metadata["palette"]["cleanup_applied"] is True


def test_explicit_ai_pixel_v2_algorithm_processes_fixture(client: TestClient, worker: JobWorker) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-ai-2.png"

    with fixture_path.open("rb") as image_file:
        create_response = client.post(
            "/api/jobs?algorithm=ai-pixel-v2&scale_mode=manual&scale=2&palette_cleanup=off",
            files={"file": ("test-ai-2.png", image_file, "image/png")},
        )

    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]
    assert worker.run_once() is True

    metadata = client.get(f"/api/jobs/{job_id}").json()
    assert metadata["status"] == "completed"
    assert metadata["algorithm_requested"] == "ai-pixel-v2"
    assert metadata["algorithm_used"] == "ai-pixel-v2"
    assert metadata["reconstruction"]["resize_method"] == "ai-pixel-v2-resampled-cluster"
    assert metadata["reconstruction"]["artifact_cleanup"] == "isolated-pixel-neighborhood"


def test_processing_failure_retries_until_max_attempts(
    client: TestClient,
    worker: JobWorker,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x4-90.jpg"

    def fail_processing(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("forced failure")

    monkeypatch.setattr("pixelreforge_api.processing.process_image_file", fail_processing)
    caplog.set_level("ERROR", logger="pixelreforge_api.processing")
    with fixture_path.open("rb") as image_file:
        create_response = client.post(
            "/api/jobs?scale=4",
            files={"file": ("test-jpegs-x4-90.jpg", image_file, "image/jpeg")},
        )

    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]
    assert run_worker_until_idle(worker, max_runs=5) == 3

    metadata = client.get(f"/api/jobs/{job_id}").json()
    assert metadata["status"] == "failed"
    assert metadata["attempts"] == 3
    assert metadata["max_attempts"] == 3
    assert metadata["last_error"] == "forced failure"
    failed = [record for record in caplog.records if record.event == "job_processing_failed"]
    assert len(failed) == 3
    assert all(record.job_id == job_id for record in failed)
    assert all(record.error_type == "RuntimeError" for record in failed)


def test_validation_failure_is_not_retried(
    client: TestClient,
    worker: JobWorker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x4-90.jpg"

    def fail_validation(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise ValueError("invalid input image")

    monkeypatch.setattr("pixelreforge_api.processing.process_image_file", fail_validation)
    with fixture_path.open("rb") as image_file:
        create_response = client.post(
            "/api/jobs?scale=4",
            files={"file": ("test-jpegs-x4-90.jpg", image_file, "image/jpeg")},
        )

    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]
    assert worker.run_once() is True
    assert worker.run_once() is False

    metadata = client.get(f"/api/jobs/{job_id}").json()
    assert metadata["status"] == "failed"
    assert metadata["attempts"] == 1
    assert metadata["last_error"] == "invalid input image"


def test_missing_job_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/jobs/missing-job")

    assert response.status_code == 404


def test_list_jobs_returns_recent_queued_jobs(client: TestClient) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x4-90.jpg"
    with fixture_path.open("rb") as image_file:
        first_response = client.post(
            "/api/jobs?scale=4",
            files={"file": ("first.jpg", image_file, "image/jpeg")},
        )
    with fixture_path.open("rb") as image_file:
        second_response = client.post(
            "/api/jobs?scale=4",
            files={"file": ("second.jpg", image_file, "image/jpeg")},
        )

    response = client.get("/api/jobs?limit=10")

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert response.status_code == 200
    payload = response.json()
    job_ids = [job["job_id"] for job in payload["jobs"]]
    assert second_response.json()["job_id"] in job_ids
    assert first_response.json()["job_id"] in job_ids


def test_worker_recovery_requeues_interrupted_processing_job(worker: JobWorker, job_store: SQLiteJobStore) -> None:
    job_id = "interrupted-processing-job"
    job_dir = get_job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = job_dir / "input.png"
    input_path.write_bytes(b"not-used")
    now = datetime.now(UTC)
    job_store.create_job(
        JobMetadata(
            job_id=job_id,
            status="processing",
            attempts=1,
            max_attempts=3,
            progress_percent=50,
            stage="grid_recovery",
            stage_message="Grid recovery...",
            input_filename="input.png",
            input_path=str(input_path.relative_to(ROOT)),
            started_at=now,
            heartbeat_at=now,
            created_at=now,
            updated_at=now,
            worker_id="test-worker",
        )
    )

    worker.recover()

    metadata = job_store.get_job(job_id)
    assert metadata is not None
    assert metadata.status == "queued"
    assert metadata.attempts == 1
    assert metadata.last_error == "Worker was interrupted."


def test_cancel_endpoint_marks_active_job_and_blocks_download(client: TestClient, job_store: SQLiteJobStore) -> None:
    job_id = "cancel-active-job-regression"
    job_dir = get_job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = job_dir / "input.png"
    input_path.write_bytes(b"not-used")
    job_store.create_job(
        JobMetadata(
            job_id=job_id,
            status="processing",
            progress_percent=35,
            stage="grid_recovery",
            stage_message="Grid recovery...",
            input_filename="input.png",
            input_path=str(input_path.relative_to(ROOT)),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )

    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")

    assert cancel_response.status_code == 200
    metadata = cancel_response.json()
    assert metadata["status"] == "cancelled"
    assert metadata["cancel_requested"] is True
    assert metadata["stage"] == "cancelled"
    assert metadata["stage_message"] == "Restoration cancelled."
    download_response = client.get(f"/api/jobs/{job_id}/download")
    assert download_response.status_code == 409


def test_process_job_records_progress_and_preserves_cancelled_status(
    worker: JobWorker,
    job_store: SQLiteJobStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = "processing-cancel-regression"
    job_dir = get_job_dir(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    input_path = job_dir / "input.png"
    input_path.write_bytes(b"not-used")
    job_store.create_job(
        JobMetadata(
            job_id=job_id,
            status="queued",
            input_filename="input.png",
            input_path=str(input_path.relative_to(ROOT)),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )

    def cancel_during_processing(_input_path, _settings, progress=None, cancel=None):  # type: ignore[no-untyped-def]
        progress("grid_recovery", 35.0, "Grid recovery...")

        def mark_cancelled(metadata: JobMetadata) -> JobMetadata:
            metadata.status = "cancelled"
            return metadata

        job_store.update_job(job_id, mark_cancelled)
        assert cancel()
        from pixelreforge_core import ProcessingCancelled

        raise ProcessingCancelled("cancelled")

    monkeypatch.setattr("pixelreforge_api.processing.process_image_file", cancel_during_processing)

    assert worker.run_once() is True

    metadata = job_store.get_job(job_id)
    assert metadata is not None
    assert metadata.status == "cancelled"
    assert metadata.stage == "cancelled"
