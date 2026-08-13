import uuid
from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from agentforge_control_plane.config import Settings, get_settings
from agentforge_control_plane.db import get_db


class AuthContext:
    """Resolved identity for the Phase-1 static-bearer-token auth shim."""

    def __init__(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id


def get_current_auth(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.dev_bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")
    return AuthContext(
        tenant_id=uuid.UUID(settings.default_tenant_id),
        user_id=uuid.UUID(settings.default_user_id),
    )


DbSession = Session
