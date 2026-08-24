from typing import Any


def create_app(*args: Any, **kwargs: Any):  # type: ignore[no-untyped-def]
    from .main import create_app as _create_app

    return _create_app(*args, **kwargs)


def __getattr__(name: str) -> Any:
    if name == "app":
        from .main import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["app", "create_app"]
