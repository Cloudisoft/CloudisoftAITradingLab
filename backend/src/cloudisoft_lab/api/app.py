from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import SecretStr

from cloudisoft_lab.api.routes import core, funds, governance, research, strategies
from cloudisoft_lab.api.security import RateLimiter, SecurityMiddleware, UserService
from cloudisoft_lab.core.config import Settings, get_settings
from cloudisoft_lab.core.logging import configure_logging, get_logger
from cloudisoft_lab.core.security import CredentialVault, hash_password
from cloudisoft_lab.db.base import create_all, make_sessionmaker
from cloudisoft_lab.db.persistence import StateStore, persistent_secret
from cloudisoft_lab.worker.factory import build_lab

log = get_logger(__name__)


def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")


def create_app(settings: Settings | None = None, run_worker: bool | None = None) -> FastAPI:
    settings = settings or get_settings()
    run_worker = settings.run_worker if run_worker is None else run_worker
    configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        sessions = make_sessionmaker(settings.database_url)
        if settings.auto_migrate:
            await asyncio.to_thread(_migrate)
        else:
            await create_all(sessions)
        app.state.settings = settings
        if settings.jwt_secret_is_default and settings.environment.value in ("staging", "production"):
            settings.jwt_secret = SecretStr(await persistent_secret(sessions, "jwt_secret"))
        key = settings.credential_encryption_key.get_secret_value() if settings.credential_encryption_key else None
        if key is None and settings.environment.value in ("staging", "production"):
            key = await persistent_secret(sessions, "credential_key")
            log.warning("security.encryption_key_in_db",
                        note="Set CLAB_CREDENTIAL_ENCRYPTION_KEY in the host's secret store for stronger encryption at rest")
        app.state.users = UserService(sessions, CredentialVault(key) if key else None)
        pw = settings.owner_password_hash.get_secret_value() if settings.owner_password_hash else None
        if pw is None and settings.owner_password:
            pw = hash_password(settings.owner_password.get_secret_value())
        await app.state.users.ensure_owner(settings.owner_email, pw)
        app.state.sessions = sessions
        app.state.setup_code = None
        if not await app.state.users.owner_exists():
            # Persisted so a restart before the owner is created doesn't invalidate the code.
            app.state.setup_code = await persistent_secret(sessions, "setup_code", lambda: secrets.token_hex(4).upper())
            # Printed only to the server log (visible to the hosting account), never returned by the API.
            log.warning("owner.setup_required", setup_code=app.state.setup_code,
                        how="Open the dashboard > Security & Audit > Create owner account, and enter this code")
        app.state.lab = lab = build_lab(settings)
        app.state.store = store = StateStore(sessions)
        restored = await store.load(lab)  # RecoveryError aborts startup on a tampered audit chain
        log.info("lab.ready", restored=restored)
        await store.save(lab)
        task = asyncio.create_task(lab.run_forever(after_tick=store.save)) if run_worker else None
        yield
        if task:
            task.cancel()
        await store.save(lab)
        await sessions.kw["bind"].dispose()

    app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan,
                  description="PAPER TRADING MODE. Live trading disabled by default. No profit is guaranteed.")
    app.add_middleware(SecurityMiddleware, limiter=RateLimiter())
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                       allow_headers=["Authorization", "Content-Type"])
    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo submitted values back (they may contain passwords, codes or keys).
        errors = [{"field": ".".join(str(p) for p in e.get("loc", [])[1:]), "message": e.get("msg", "invalid")}
                  for e in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    for r in (core.router, research.router, strategies.router, funds.router, governance.router):
        app.include_router(r)
    return app


app = create_app()
