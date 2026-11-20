from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Numeric, String, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

MONEY = Numeric(28, 10)


class Base(DeclarativeBase):
    type_annotation_map = {Decimal: MONEY, dict: JSON, dt.datetime: DateTime(timezone=True)}


def uid() -> str:
    return uuid.uuid4().hex


class IdMixin:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


def make_sessionmaker(url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


async def create_all(sessions: async_sessionmaker[AsyncSession]) -> None:
    """Test/dev helper. Production uses Alembic (``alembic upgrade head``)."""
    from cloudisoft_lab.db import models  # noqa: F401

    async with sessions.kw["bind"].begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
