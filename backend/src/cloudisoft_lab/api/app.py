from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
        app.state.users = UserService(sessions, CredentialVault(key) if key else None)
        pw = settings.owner_password_hash.get_secret_value() if settings.owner_password_hash else None
        if pw is None and settings.owner_password:
            pw = hash_password(settings.owner_password.get_secret_value())
        await app.state.users.ensure_owner(settings.owner_email, pw)
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
    for r in (core.router, research.router, strategies.router, funds.router, governance.router):
        app.include_router(r)
    return app


app = create_app()
