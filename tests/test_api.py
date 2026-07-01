from pathlib import Path
import json
import sys
import types

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from pixelreforge_api import app, create_app  # noqa: E402
from pixelreforge_api.sentry_config import configure_sentry  # noqa: E402
from pixelreforge_api.settings import ApiSettings, load_settings  # noqa: E402
from pixelreforge_api.storage import get_metadata_path  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


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

    settings = load_settings()

    assert settings.env == "production"
    assert settings.debug is True
    assert settings.log_level == "ERROR"
    assert settings.log_format == "json"
    assert settings.sentry_dsn == "https://public@example.invalid/1"
    assert settings.sentry_traces_sample_rate == 0.25


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


def test_create_job_processes_fixture_and_downloads_result(client: TestClient) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x4-90.jpg"

    with fixture_path.open("rb") as image_file:
        create_response = client.post(
            "/api/jobs?scale=4",
            files={"file": ("test-jpegs-x4-90.jpg", image_file, "image/jpeg")},
        )

    assert create_response.status_code == 202
    create_payload = create_response.json()
    job_id = create_payload["job_id"]

    status_response = client.get(f"/api/jobs/{job_id}")
    assert status_response.status_code == 200
    metadata = status_response.json()
    assert metadata["status"] == "completed"
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


def test_auto_algorithm_records_recommendation_and_fallback(client: TestClient) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x4-60.jpg"

    with fixture_path.open("rb") as image_file:
        create_response = client.post(
            "/api/jobs?algorithm=auto&scale_mode=auto&min_scale=2&max_scale=16&palette_cleanup=light",
            files={"file": ("test-jpegs-x4-60.jpg", image_file, "image/jpeg")},
        )

    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]

    metadata = client.get(f"/api/jobs/{job_id}").json()
    assert metadata["algorithm_requested"] == "auto"
    assert metadata["algorithm_used"] == "noisy-pixel-v1"
    assert metadata["reconstruction"]["resize_method"] == "dominant-color-cluster"
    assert metadata["palette_cleanup"] == "light"
    assert metadata["palette"]["cleanup_applied"] is True
    assert "color_count_after" in metadata["palette"]
    assert metadata["analysis"]["recommended_algorithm"] == "noisy-pixel-v1"


def test_explicit_noisy_pixel_algorithm_processes_fixture(client: TestClient) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-jpegs-x10-60.jpg"

    with fixture_path.open("rb") as image_file:
        create_response = client.post(
            "/api/jobs?algorithm=noisy-pixel-v1&scale_mode=auto&min_scale=2&max_scale=16&palette_cleanup=medium",
            files={"file": ("test-jpegs-x10-60.jpg", image_file, "image/jpeg")},
        )

    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]

    metadata = client.get(f"/api/jobs/{job_id}").json()
    assert metadata["status"] == "completed"
    assert metadata["algorithm_used"] == "noisy-pixel-v1"
    assert metadata["target_size"] == [32, 32]
    assert metadata["palette"]["cleanup_applied"] is True


def test_explicit_ai_pixel_v2_algorithm_processes_fixture(client: TestClient) -> None:
    fixture_path = ROOT / "tests" / "fixtures" / "test-ai-2.png"

    with fixture_path.open("rb") as image_file:
        create_response = client.post(
            "/api/jobs?algorithm=ai-pixel-v2&scale_mode=manual&scale=2&palette_cleanup=off",
            files={"file": ("test-ai-2.png", image_file, "image/png")},
        )

    assert create_response.status_code == 202
    job_id = create_response.json()["job_id"]

    metadata = client.get(f"/api/jobs/{job_id}").json()
    assert metadata["status"] == "completed"
    assert metadata["algorithm_requested"] == "ai-pixel-v2"
    assert metadata["algorithm_used"] == "ai-pixel-v2"
    assert metadata["reconstruction"]["resize_method"] == "ai-pixel-v2-resampled-cluster"
    assert metadata["reconstruction"]["artifact_cleanup"] == "isolated-pixel-neighborhood"


def test_processing_failure_is_logged_with_job_id(client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
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
    metadata = client.get(f"/api/jobs/{job_id}").json()
    assert metadata["status"] == "failed"
    failed = [record for record in caplog.records if record.event == "job_processing_failed"]
    assert len(failed) == 1
    assert failed[0].job_id == job_id
    assert failed[0].error_type == "RuntimeError"


def test_empty_metadata_file_returns_not_found(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    job_id = "empty-metadata-regression"
    metadata_path = get_metadata_path(job_id)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text("", encoding="utf-8")
    caplog.set_level("WARNING", logger="pixelreforge_api.storage")

    response = client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 404
    assert any(record.event == "job_metadata_unreadable" for record in caplog.records)
