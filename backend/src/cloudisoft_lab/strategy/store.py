"""Versioned strategy store. Versions are immutable; every change creates a new version.
Only one strategy is ACTIVE in the paper loop; promotion requires an approved proposal."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from cloudisoft_lab.strategy.schema import StrategyDefinition

STATUSES = ("research", "paper", "paused", "retired")


@dataclass
class StrategyVersionRec:
    version: int
    definition: StrategyDefinition
    fingerprint: str
    author: str
    change_note: str
    created_at: str
    backtests: list[dict[str, object]] = field(default_factory=list)


@dataclass
class StrategyRec:
    id: str
    name: str
    status: str
    versions: list[StrategyVersionRec]

    @property
    def latest(self) -> StrategyVersionRec:
        return self.versions[-1]


class StrategyStoreError(RuntimeError):
    pass


@dataclass
class StrategyStore:
    items: dict[str, StrategyRec] = field(default_factory=dict)

    def create(self, d: StrategyDefinition, author: str, note: str = "created") -> StrategyRec:
        d = d.model_copy(update={"version": 1})
        rec = StrategyRec(uuid.uuid4().hex, d.name, "research",
                          [StrategyVersionRec(1, d, d.fingerprint(), author, note, _now())])
        self.items[rec.id] = rec
        return rec

    def add_version(self, sid: str, d: StrategyDefinition, author: str, note: str) -> StrategyVersionRec:
        rec = self.items[sid]
        if d.fingerprint() == rec.latest.fingerprint:
            raise StrategyStoreError("no change from latest version")
        v = rec.latest.version + 1
        d = d.model_copy(update={"version": v})
        ver = StrategyVersionRec(v, d, d.fingerprint(), author, note, _now())
        rec.versions.append(ver)
        return ver

    def set_status(self, sid: str, status: str) -> StrategyRec:
        if status not in STATUSES:
            raise StrategyStoreError(f"invalid status {status}")
        if status == "paper":
            for other in self.items.values():
                if other.status == "paper" and other.id != sid:
                    other.status = "paused"
        self.items[sid].status = status
        return self.items[sid]

    def active(self) -> StrategyRec | None:
        return next((s for s in self.items.values() if s.status == "paper"), None)

    def rollback(self, sid: str, to_version: int, author: str) -> StrategyVersionRec:
        rec = self.items[sid]
        old = next((v for v in rec.versions if v.version == to_version), None)
        if old is None:
            raise StrategyStoreError("version not found")
        return self.add_version(sid, old.definition, author, f"rollback to v{to_version}")


def compare(results: dict[str, dict[str, float | None]]) -> list[dict[str, object]]:
    """Rank backtest metric dicts by Sharpe, then max drawdown."""
    rows = [{"id": k, **v} for k, v in results.items()]
    return sorted(rows, key=lambda r: (-(r.get("sharpe") or 0), -(r.get("max_drawdown") or -1)))


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()
