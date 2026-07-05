from dataclasses import dataclass
import os
from pathlib import Path


VALID_ENVS = {"development", "production", "test"}
VALID_LOG_FORMATS = {"json", "plain"}
DEFAULT_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def _read_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_env() -> str:
    value = os.getenv("PIXELREFORGE_ENV", "development").strip().lower()
    if value not in VALID_ENVS:
        return "development"
    return value


@dataclass(frozen=True)
class ApiSettings:
    env: str
    debug: bool
    log_level: str
    log_format: str
    sentry_dsn: str | None
    sentry_traces_sample_rate: float
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS
    root: Path = Path.cwd()
    database_url: str = ""
    job_max_attempts: int = 3
    job_timeout_seconds: int = 30 * 60
    job_ttl_seconds: int = 24 * 60 * 60
    worker_concurrency: int = 1
    worker_poll_interval_seconds: float = 1.0
    worker_heartbeat_interval_seconds: float = 10.0
    worker_id: str = "default"

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def log_successful_requests(self) -> bool:
        return self.is_production


def load_settings() -> ApiSettings:
    env = _read_env()
    root = Path(os.getenv("PIXELREFORGE_ROOT", Path.cwd())).resolve()
    debug = _read_bool("PIXELREFORGE_DEBUG", default=False)
    default_level = "DEBUG" if debug else "INFO"
    log_level = os.getenv("PIXELREFORGE_LOG_LEVEL", default_level).strip().upper()
    default_format = "json" if env == "production" else "plain"
    log_format = os.getenv("PIXELREFORGE_LOG_FORMAT", default_format).strip().lower()
    if log_format not in VALID_LOG_FORMATS:
        log_format = default_format
    sentry_traces_sample_rate = _read_float("PIXELREFORGE_SENTRY_TRACES_SAMPLE_RATE", default=0.0)
    database_url = os.getenv("PIXELREFORGE_DATABASE_URL") or f"sqlite:///{root / 'runtime' / 'pixelreforge.sqlite3'}"

    return ApiSettings(
        env=env,
        debug=debug,
        log_level=log_level,
        log_format=log_format,
        sentry_dsn=os.getenv("PIXELREFORGE_SENTRY_DSN") or None,
        sentry_traces_sample_rate=sentry_traces_sample_rate,
        cors_origins=_read_csv("PIXELREFORGE_CORS_ORIGINS", default=DEFAULT_CORS_ORIGINS),
        root=root,
        database_url=database_url,
        job_max_attempts=_read_int("PIXELREFORGE_JOB_MAX_ATTEMPTS", default=3, minimum=1),
        job_timeout_seconds=_read_int("PIXELREFORGE_JOB_TIMEOUT_SECONDS", default=30 * 60, minimum=1),
        job_ttl_seconds=_read_int("PIXELREFORGE_JOB_TTL_SECONDS", default=24 * 60 * 60, minimum=1),
        worker_concurrency=_read_int("PIXELREFORGE_WORKER_CONCURRENCY", default=1, minimum=1),
        worker_poll_interval_seconds=_read_float("PIXELREFORGE_WORKER_POLL_INTERVAL_SECONDS", default=1.0, minimum=0.05),
        worker_heartbeat_interval_seconds=_read_float("PIXELREFORGE_WORKER_HEARTBEAT_INTERVAL_SECONDS", default=10.0, minimum=0.5),
        worker_id=os.getenv("PIXELREFORGE_WORKER_ID", "default").strip() or "default",
    )


def _read_int(name: str, default: int, minimum: int | None = None) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if minimum is not None and parsed < minimum:
        return default
    return parsed


def _read_float(name: str, default: float, minimum: float | None = None) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    if minimum is not None and parsed < minimum:
        return default
    return parsed


def _read_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None:
        return default
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default
