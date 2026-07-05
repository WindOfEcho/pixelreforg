from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import hmac
import string
import time
from uuid import uuid4


SESSION_TOKEN_VERSION = "v1"


@dataclass(frozen=True)
class AnonymousSession:
    session_id: str
    token: str
    should_set_cookie: bool


def resolve_anonymous_session(
    raw_token: str | None,
    *,
    secret: str,
    max_age_seconds: int,
    now: int | None = None,
) -> AnonymousSession:
    current_time = int(time.time()) if now is None else now
    session_id = _session_id_from_token(raw_token, secret=secret, now=current_time)
    if session_id is not None and raw_token is not None:
        return AnonymousSession(session_id=session_id, token=raw_token, should_set_cookie=False)
    return create_anonymous_session(secret=secret, max_age_seconds=max_age_seconds, now=current_time)


def create_anonymous_session(*, secret: str, max_age_seconds: int, now: int | None = None) -> AnonymousSession:
    current_time = int(time.time()) if now is None else now
    session_id = uuid4().hex
    expires_at = current_time + max_age_seconds
    token = _sign_session(session_id=session_id, expires_at=expires_at, secret=secret)
    return AnonymousSession(session_id=session_id, token=token, should_set_cookie=True)


def _session_id_from_token(raw_token: str | None, *, secret: str, now: int) -> str | None:
    if raw_token is None:
        return None
    parts = raw_token.split(".")
    if len(parts) != 4:
        return None
    version, session_id, expires_value, signature = parts
    if version != SESSION_TOKEN_VERSION or not _is_valid_session_id(session_id):
        return None
    try:
        expires_at = int(expires_value)
    except ValueError:
        return None
    if expires_at <= now:
        return None

    payload = _session_payload(session_id=session_id, expires_at=expires_at)
    expected_signature = _signature(payload, secret=secret)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    return session_id


def _sign_session(*, session_id: str, expires_at: int, secret: str) -> str:
    payload = _session_payload(session_id=session_id, expires_at=expires_at)
    return f"{payload}.{_signature(payload, secret=secret)}"


def _session_payload(*, session_id: str, expires_at: int) -> str:
    return f"{SESSION_TOKEN_VERSION}.{session_id}.{expires_at}"


def _signature(payload: str, *, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _is_valid_session_id(session_id: str) -> bool:
    return len(session_id) == 32 and all(character in string.hexdigits for character in session_id)
