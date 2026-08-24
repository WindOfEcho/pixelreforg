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


def create_job_without_processing(
    client: TestClient, fixture_name: str = "zephyr-small-test-x2.png"
) -> str:
    fixture_path = ROOT / "tests" / "fixtures" / fixture_name
    with fixture_path.open("rb") as image_file:
        response = client.post(
            "/api/jobs?scale=2",
            files={"file": (fixture_name, image_file, "image/png")},
        )
    assert response.status_code == 202
    return response.json()["job_id"]


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "x-request-id" in response.headers


def test_request_id_header_is_preserved(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-id"


def test_production_request_logging_records_successful_requests(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PIXELREFORGE_ENV", "production")
    monkeypatch.setenv("PIXELREFORGE_LOG_FORMAT", "json")
    monkeypatch.setenv("PIXELREFORGE_LOG_LEVEL", "INFO")
    monkeypatch.setenv("PIXELREFORGE_SESSION_SECRET", "test-production-session-secret")
    production_app = create_app()
    production_client = TestClient(production_app)

    response = production_client.get(
        "/health", headers={"X-Request-ID": "prod-request-id"}
    )

    assert response.status_code == 200
    log_lines = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{")
    ]
    finished = [record for record in log_lines if record["event"] == "request_finished"]
    assert len(finished) == 1
    assert finished[0]["request_id"] == "prod-request-id"
    assert finished[0]["status_code"] == 200


def test_settings_read_runtime_mode_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PIXELREFORGE_ENV", "production")
    monkeypatch.setenv("PIXELREFORGE_DEBUG", "true")
    monkeypatch.setenv("PIXELREFORGE_LOG_FORMAT", "json")
    monkeypatch.setenv("PIXELREFORGE_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("PIXELREFORGE_SENTRY_DSN", "https://public@example.invalid/1")
    monkeypatch.setenv("PIXELREFORGE_SENTRY_TRACES_SAMPLE_RATE", "0.25")
    monkeypatch.setenv("PIXELREFORGE_CORS_ORIGINS", "https://example.com")
    monkeypatch.setenv("PIXELREFORGE_SESSION_SECRET", "test-production-session-secret")

    settings = load_settings()

    assert settings.env == "production"
    assert settings.debug is True
    assert settings.log_level == "ERROR"
    assert settings.log_format == "json"
    assert settings.sentry_dsn == "https://public@example.invalid/1"
    assert settings.sentry_traces_sample_rate == 0.25
    assert settings.cors_origins == ("https://example.com",)


def test_production_settings_require_session_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PIXELREFORGE_ENV", "production")
    monkeypatch.delenv("PIXELREFORGE_SESSION_SECRET", raising=False)

    with pytest.raises(ValueError, match="PIXELREFORGE_SESSION_SECRET"):
        load_settings()


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


def test_sentry_is_configured_with_dsn(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
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


@pytest.mark.regression
def test_create_job_processes_fixture_and_downloads_result(
    client: TestClient, worker: JobWorker
) -> None:
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
    assert client.cookies.get("pixelreforge_session") is not None

    assert worker.run_once() is True

    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.status_code == 200
    metadata = status_response.json()
    assert metadata["status"] == "completed"
    assert "owner_id" not in metadata
    assert "input_path" not in metadata
    assert "output_path" not in metadata
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


@pytest.mark.regression
def test_auto_algorithm_records_recommendation_and_fallback(
    client: TestClient, worker: JobWorker
) -> None:
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


@pytest.mark.regression
def test_explicit_noisy_pixel_algorithm_processes_fixture(
    client: TestClient, worker: JobWorker
) -> None:
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


def test_explicit_ai_grid_hypothesis_algorithm_processes_tiny_fixture(
    client: TestClient, worker: JobWorker
) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "zephyr-small-test-x2.png"

    with fixture_path.open("rb") as image_file:
        create_response = client.post(
            "/api/jobs?algorithm=ai-grid-hypothesis-v1&scale_mode=auto&min_scale=2&max_scale=8&palette_cleanup=off",
            files={"file": ("zephyr-small-test-x2.png", image_file, "image/png")},
        )

    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]
    assert worker.run_once() is True

    metadata = client.get(f"/api/jobs/{job_id}").json()
    assert metadata["status"] == "completed"
    assert metadata["algorithm_requested"] == "ai-grid-hypothesis-v1"
    assert metadata["algorithm_used"] == "ai-grid-hypothesis-v1"
    assert (
        metadata["reconstruction"]["resize_method"]
        == "ai-grid-hypothesis-v1-resampled-cluster"
    )
    assert metadata["target_size"][0] < metadata["source_size"][0]


@pytest.mark.performance
def test_explicit_ai_pixel_v2_algorithm_processes_fixture(
    client: TestClient, worker: JobWorker
) -> None:
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
    assert (
        metadata["reconstruction"]["resize_method"] == "ai-pixel-v2-resampled-cluster"
    )
    assert (
        metadata["reconstruction"]["artifact_cleanup"] == "isolated-pixel-neighborhood"
    )


@pytest.mark.regression
def test_processing_failure_retries_until_max_attempts(
    client: TestClient,
    worker: JobWorker,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x4-90.jpg"

    def fail_processing(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("forced failure")

    monkeypatch.setattr(
        "pixelreforge_api.processing.process_image_file", fail_processing
    )
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
    failed = [
        record for record in caplog.records if record.event == "job_processing_failed"
    ]
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

    monkeypatch.setattr(
        "pixelreforge_api.processing.process_image_file", fail_validation
    )
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


def test_same_anonymous_session_keeps_access_after_client_reload(
    api_settings: ApiSettings, job_store: SQLiteJobStore
) -> None:
    app = create_app(settings=api_settings, job_store=job_store)
    first_client = TestClient(app)
    reloaded_client = TestClient(app)
    job_id = create_job_without_processing(first_client)
    session_cookie = first_client.cookies.get(api_settings.session_cookie_name)
    assert session_cookie is not None
    reloaded_client.cookies.set(
        api_settings.session_cookie_name,
        session_cookie,
        domain="testserver.local",
        path="/",
    )

    response = reloaded_client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["job_id"] == job_id


def test_anonymous_sessions_isolate_job_status_list_download_and_cancel(
    api_settings: ApiSettings, job_store: SQLiteJobStore
) -> None:
    app = create_app(settings=api_settings, job_store=job_store)
    owner_client = TestClient(app)
    other_client = TestClient(app)
    job_id = create_job_without_processing(owner_client)

    def complete_job(metadata: JobMetadata) -> JobMetadata:
        output_path = get_job_dir(job_id) / "output.png"
        output_path.write_bytes(b"\x89PNG\r\n\x1a\nowned")
        metadata.status = "completed"
        metadata.progress_percent = 100
        metadata.stage = "completed"
        metadata.output_path = str(output_path.relative_to(ROOT))
        return metadata

    assert job_store.update_job(job_id, complete_job) is not None

    assert owner_client.get(f"/api/jobs/{job_id}").status_code == 200
    owner_download = owner_client.get(f"/api/jobs/{job_id}/download")
    assert owner_download.status_code == 200
    assert owner_download.content.startswith(b"\x89PNG")

    assert other_client.get(f"/api/jobs/{job_id}").status_code == 404
    assert other_client.get(f"/api/jobs/{job_id}/download").status_code == 404
    assert other_client.post(f"/api/jobs/{job_id}/cancel").status_code == 404
    list_response = other_client.get("/api/jobs?limit=10")
    assert list_response.status_code == 200
    assert job_id not in [job["job_id"] for job in list_response.json()["jobs"]]


def test_invalid_anonymous_session_cookie_starts_new_session_without_old_access(
    api_settings: ApiSettings,
    job_store: SQLiteJobStore,
) -> None:
    app = create_app(settings=api_settings, job_store=job_store)
    owner_client = TestClient(app)
    invalid_client = TestClient(app)
    invalid_client.cookies.set(
        api_settings.session_cookie_name,
        "invalid-token",
        domain="testserver.local",
        path="/",
    )
    job_id = create_job_without_processing(owner_client)
    owner_cookie = owner_client.cookies.get(api_settings.session_cookie_name)

    response = invalid_client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 404
    invalid_cookie = invalid_client.cookies.get(
        api_settings.session_cookie_name, domain="testserver.local", path="/"
    )
    assert invalid_cookie is not None
    assert invalid_cookie != owner_cookie


def test_list_jobs_returns_recent_queued_jobs(client: TestClient) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "zephyr-small-test-x2.png"
    with fixture_path.open("rb") as image_file:
        first_response = client.post(
            "/api/jobs?scale=2",
            files={"file": ("first.png", image_file, "image/png")},
        )
    with fixture_path.open("rb") as image_file:
        second_response = client.post(
            "/api/jobs?scale=2",
            files={"file": ("second.png", image_file, "image/png")},
        )

    response = client.get("/api/jobs?limit=10")

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert response.status_code == 200
    payload = response.json()
    job_ids = [job["job_id"] for job in payload["jobs"]]
    assert second_response.json()["job_id"] in job_ids
    assert first_response.json()["job_id"] in job_ids


def test_worker_recovery_requeues_interrupted_processing_job(
    worker: JobWorker, job_store: SQLiteJobStore
) -> None:
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


def test_cancel_endpoint_marks_active_job_and_blocks_download(
    client: TestClient, job_store: SQLiteJobStore
) -> None:
    job_id = create_job_without_processing(client)

    def mark_processing(metadata: JobMetadata) -> JobMetadata:
        metadata.status = "processing"
        metadata.progress_percent = 35
        metadata.stage = "grid_recovery"
        metadata.stage_message = "Grid recovery..."
        metadata.created_at = datetime.now(UTC)
        metadata.updated_at = datetime.now(UTC)
        return metadata

    assert job_store.update_job(job_id, mark_processing) is not None

    cancel_response = client.post(f"/api/jobs/{job_id}/cancel")

    assert cancel_response.status_code == 200
    metadata = cancel_response.json()
    assert metadata["status"] == "cancelled"
    assert metadata["cancel_requested"] is True
    assert metadata["stage"] == "cancelled"
    assert metadata["stage_message"] == "Restoration cancelled."
    download_response = client.get(f"/api/jobs/{job_id}/download")
    assert download_response.status_code == 409


@pytest.mark.regression
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

    monkeypatch.setattr(
        "pixelreforge_api.processing.process_image_file", cancel_during_processing
    )

    assert worker.run_once() is True

    metadata = job_store.get_job(job_id)
    assert metadata is not None
    assert metadata.status == "cancelled"
    assert metadata.stage == "cancelled"
