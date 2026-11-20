from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cloudisoft_lab.api.routes.core import router
from cloudisoft_lab.core.config import Settings, get_settings
from cloudisoft_lab.core.logging import configure_logging
from cloudisoft_lab.worker.factory import build_lab


def create_app(settings: Settings | None = None, run_worker: bool | None = None) -> FastAPI:
    settings = settings or get_settings()
    run_worker = settings.run_worker if run_worker is None else run_worker
    configure_logging(settings.log_level, settings.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.lab = build_lab(settings)
        task = asyncio.create_task(app.state.lab.run_forever()) if run_worker else None
        yield
        if task:
            task.cancel()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan,
                  description="PAPER TRADING MODE. Live trading disabled by default.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                       allow_headers=["Authorization", "Content-Type"])
    app.include_router(router)
    return app


app = create_app()
