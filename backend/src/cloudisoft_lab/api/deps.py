from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cloudisoft_lab.api.security import UserService
from cloudisoft_lab.core.config import get_settings
from cloudisoft_lab.core.security import decode_access_token
from cloudisoft_lab.db.persistence import StateStore
from cloudisoft_lab.worker.lab import Lab

bearer = HTTPBearer(auto_error=False)


def get_lab(request: Request) -> Lab:
    return request.app.state.lab  # type: ignore[no-any-return]


def get_users(request: Request) -> UserService:
    return request.app.state.users  # type: ignore[no-any-return]


async def persist(request: Request) -> None:
    """Call after every owner/operator mutation so state survives a restart."""
    store: StateStore | None = getattr(request.app.state, "store", None)
    if store is not None:
        await store.save(request.app.state.lab)


def current_user(creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict[str, str]:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required")
    try:
        return decode_access_token(creds.credentials, get_settings().jwt_secret.get_secret_value())
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc


def require_role(*roles: str):  # type: ignore[no-untyped-def]
    def dep(user: Annotated[dict[str, str], Depends(current_user)]) -> dict[str, str]:
        if user.get("role") not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user
    return dep


LabDep = Annotated[Lab, Depends(get_lab)]
Users = Annotated[UserService, Depends(get_users)]
Owner = Annotated[dict[str, str], Depends(require_role("owner"))]
Operator = Annotated[dict[str, str], Depends(require_role("owner", "operator"))]
Viewer = Annotated[dict[str, str], Depends(require_role("owner", "operator", "viewer"))]
