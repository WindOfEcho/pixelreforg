import logging

from .settings import ApiSettings


logger = logging.getLogger(__name__)


def configure_sentry(settings: ApiSettings) -> None:
    if settings.sentry_dsn is None:
        logger.info("Sentry disabled.", extra={"event": "sentry_disabled"})
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR,
    )
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        integrations=[FastApiIntegration(), sentry_logging],
        traces_sample_rate=settings.sentry_traces_sample_rate,
        send_default_pii=False,
    )
    logger.info(
        "Sentry configured.",
        extra={
            "event": "sentry_configured",
            "env": settings.env,
            "traces_sample_rate": settings.sentry_traces_sample_rate,
        },
    )
