from __future__ import annotations

import hmac
from collections.abc import Iterator

from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def require_api_key(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    """Shared-secret auth. Disabled when API_KEY is unset (local dev). Not multi-user auth."""
    configured = request.app.state.settings.api_key
    if configured is None:
        return
    supplied = (x_api_key or "").encode()
    if not hmac.compare_digest(supplied, configured.get_secret_value().encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
