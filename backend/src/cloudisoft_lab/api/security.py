"""Users (DB-backed), TOTP two-factor, login throttling, rate limiting and security headers."""

from __future__ import annotations

import time
from collections import defaultdict, deque

import pyotp
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from cloudisoft_lab.core.security import CredentialVault, hash_password, verify_password
from cloudisoft_lab.db.models import SecurityEvent, User

ROLES = ("owner", "operator", "viewer")


class UserService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], vault: CredentialVault | None) -> None:
        self.sessions, self.vault = sessions, vault

    async def ensure_owner(self, email: str | None, password_hash: str | None) -> None:
        if not email or not password_hash:
            return
        async with self.sessions() as s, s.begin():
            u = await s.scalar(select(User).where(User.email == email))
            if u is None:
                s.add(User(email=email, password_hash=password_hash, role="owner"))

    async def authenticate(self, email: str, password: str, otp: str | None, ip: str | None) -> User | None:
        async with self.sessions() as s, s.begin():
            u = await s.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
            ok = u is not None and verify_password(password, u.password_hash)
            if ok and u is not None and u.totp_secret_enc:
                ok = bool(otp) and self.vault is not None and pyotp.TOTP(
                    self.vault.decrypt(u.totp_secret_enc)).verify(otp or "", valid_window=1)
            s.add(SecurityEvent(kind="login_success" if ok else "login_failure", severity="info" if ok else "warning",
                                detail={"email": email}, ip=ip))
            return u if ok else None

    async def create_user(self, email: str, password: str, role: str) -> User:
        if role not in ROLES or role == "owner":
            raise ValueError("role must be operator or viewer (there is exactly one owner)")
        if len(password) < 12:
            raise ValueError("password must be at least 12 characters")
        async with self.sessions() as s, s.begin():
            u = User(email=email, password_hash=hash_password(password), role=role)
            s.add(u)
        return u

    async def list_users(self) -> list[dict[str, object]]:
        async with self.sessions() as s:
            rows = (await s.scalars(select(User))).all()
            return [{"email": u.email, "role": u.role, "active": u.is_active, "totp": bool(u.totp_secret_enc)}
                    for u in rows]

    async def begin_totp(self, email: str) -> tuple[str, str]:
        if self.vault is None:
            raise ValueError("credential encryption key not configured")
        secret = pyotp.random_base32()
        return secret, pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="Cloudisoft AI Trading Lab")

    async def confirm_totp(self, email: str, secret: str, code: str) -> bool:
        if self.vault is None or not pyotp.TOTP(secret).verify(code, valid_window=1):
            return False
        async with self.sessions() as s, s.begin():
            u = await s.scalar(select(User).where(User.email == email))
            if u is None:
                return False
            u.totp_secret_enc = self.vault.encrypt(secret)
            s.add(SecurityEvent(kind="totp_enabled", severity="info", detail={"email": email}))
        return True

    async def security_events(self, limit: int = 100) -> list[dict[str, object]]:
        async with self.sessions() as s:
            rows = (await s.scalars(select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit))).all()
            return [{"at": str(r.created_at), "kind": r.kind, "severity": r.severity, "detail": r.detail, "ip": r.ip}
                    for r in rows]


class RateLimiter:
    """Sliding-window limiter (in-process; use Redis when running multiple replicas)."""

    def __init__(self) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window: float) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter, mutations_per_minute: int = 60,  # type: ignore[no-untyped-def]
                 logins_per_minute: int = 5) -> None:
        super().__init__(app)
        self.limiter, self.mpm, self.lpm = limiter, mutations_per_minute, logins_per_minute

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        ip = request.client.host if request.client else "unknown"
        if request.url.path == "/api/auth/token" and not self.limiter.allow(f"login:{ip}", self.lpm, 60):
            return JSONResponse({"detail": "too many login attempts"}, status_code=429)
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and not self.limiter.allow(f"mut:{ip}", self.mpm, 60):
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        response: Response = await call_next(request)
        h = response.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "no-referrer"
        h["Cache-Control"] = "no-store"
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
