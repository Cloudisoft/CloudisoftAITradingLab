"""Tamper-evident audit trail (hash chain). Persisted to DB via db.repository."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    seq: int
    at: str
    event: str
    actor: str
    data: dict[str, Any]
    prev_hash: str
    hash: str


@dataclass
class AuditTrail:
    events: list[AuditEvent] = field(default_factory=list)
    sink: Any = None  # optional callable(AuditEvent) for persistence

    def record(self, event: str, actor: str, data: dict[str, Any]) -> AuditEvent:
        prev = self.events[-1].hash if self.events else "GENESIS"
        at = dt.datetime.now(dt.UTC).isoformat()
        body = json.dumps({"seq": len(self.events), "at": at, "event": event, "actor": actor,
                           "data": data, "prev": prev}, sort_keys=True, default=str)
        h = hashlib.sha256(body.encode()).hexdigest()
        ev = AuditEvent(len(self.events), at, event, actor, json.loads(json.dumps(data, default=str)), prev, h)
        self.events.append(ev)
        if self.sink:
            self.sink(ev)
        return ev

    def verify(self) -> bool:
        prev = "GENESIS"
        for ev in self.events:
            body = json.dumps({"seq": ev.seq, "at": ev.at, "event": ev.event, "actor": ev.actor,
                               "data": ev.data, "prev": prev}, sort_keys=True, default=str)
            if ev.prev_hash != prev or hashlib.sha256(body.encode()).hexdigest() != ev.hash:
                return False
            prev = ev.hash
        return True
