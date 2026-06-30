from dataclasses import dataclass
import os


VALID_ENVS = {"development", "production", "test"}
VALID_LOG_FORMATS = {"json", "plain"}


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

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def log_successful_requests(self) -> bool:
        return self.is_production


def load_settings() -> ApiSettings:
    env = _read_env()
    debug = _read_bool("PIXELREFORGE_DEBUG", default=False)
    default_level = "DEBUG" if debug else "INFO"
    log_level = os.getenv("PIXELREFORGE_LOG_LEVEL", default_level).strip().upper()
    default_format = "json" if env == "production" else "plain"
    log_format = os.getenv("PIXELREFORGE_LOG_FORMAT", default_format).strip().lower()
    if log_format not in VALID_LOG_FORMATS:
        log_format = default_format
    sentry_traces_sample_rate = _read_float("PIXELREFORGE_SENTRY_TRACES_SAMPLE_RATE", default=0.0)

    return ApiSettings(
        env=env,
        debug=debug,
        log_level=log_level,
        log_format=log_format,
        sentry_dsn=os.getenv("PIXELREFORGE_SENTRY_DSN") or None,
        sentry_traces_sample_rate=sentry_traces_sample_rate,
    )


def _read_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default
