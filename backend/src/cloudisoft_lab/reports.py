"""Daily / monthly financial reports and owner notifications."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx

from cloudisoft_lab.core.logging import get_logger

if TYPE_CHECKING:
    from cloudisoft_lab.worker.lab import Lab

log = get_logger(__name__)


def build_report(lab: Lab, period: str = "daily", now: dt.datetime | None = None) -> dict[str, object]:
    now = now or dt.datetime.now(dt.UTC)
    since = now - (dt.timedelta(days=1) if period == "daily" else dt.timedelta(days=30))
    s = lab.ledger.summary(since=since, until=now + dt.timedelta(seconds=1))
    total = lab.ledger.summary()
    r = lab.survival_report(now)
    trades = [t for t in lab.closed_trades if t.closed_at >= since]
    rec = lab.withdrawal_recommendation()
    out = {
        "period": period, "from": since.isoformat(), "to": now.isoformat(),
        "survival_state": r.state, "runway_days": str(r.runway_days) if r.runway_days else None,
        "period_ledger": {k: str(v) for k, v in s.items()}, "lifetime_ledger": {k: str(v) for k, v in total.items()},
        "paper": {"equity": str(lab.paper.equity()), "cash": str(lab.paper.cash),
                  "realised_pnl": str(lab.paper.realised_pnl), "fees": str(lab.paper.fees_paid),
                  "closed_trades_in_period": len(trades),
                  "net_pnl_in_period": str(sum((t.net_pnl for t in trades), Decimal(0)))},
        "withdrawal_recommendation": {"amount": str(rec.recommended_amount), "reasons": rec.reasons, "label": rec.label},
        "pending_proposals": len(lab.board.pending()),
        "labels": "paper figures are SIMULATED; ledger figures are ACTUAL; runway is ESTIMATED",
    }
    out["markdown"] = to_markdown(out)
    return out


def to_markdown(r: dict[str, object]) -> str:
    pl = r["period_ledger"]  # type: ignore[index]
    p = r["paper"]  # type: ignore[index]
    return "\n".join([
        f"# Cloudisoft {r['period']} report ({str(r['from'])[:10]} → {str(r['to'])[:10]})",
        f"**Survival state:** {r['survival_state']} · runway: {r['runway_days'] or 'n/a'} days (estimated)",
        "## Actual economics (period)",
        f"- Net trading profit: {pl['net_trading_profit']}",  # type: ignore[index]
        f"- Verified external revenue: {pl['verified_external_revenue']}",  # type: ignore[index]
        f"- Operating expenses: {pl['operating_expenses']}",  # type: ignore[index]
        f"- Net operating profit: {pl['net_operating_profit']}",  # type: ignore[index]
        "## Paper trading (simulated)",
        f"- Equity {p['equity']} · realised P&L {p['realised_pnl']} · fees {p['fees']}",  # type: ignore[index]
        f"- Closed trades in period: {p['closed_trades_in_period']} · net {p['net_pnl_in_period']}",  # type: ignore[index]
        f"## Pending owner decisions: {r['pending_proposals']}",
        "_Past and simulated performance does not guarantee future results._",
    ])


@dataclass
class Notifier:
    webhook_url: str | None = None
    sent: list[dict[str, object]] = field(default_factory=list)

    async def notify(self, kind: str, message: str, severity: str = "info") -> None:
        event = {"at": dt.datetime.now(dt.UTC).isoformat(), "kind": kind, "severity": severity, "message": message}
        self.sent.append(event)
        self.sent = self.sent[-500:]
        log.info("owner.notify", **event)
        if self.webhook_url and self.webhook_url.startswith("https://"):
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    await c.post(self.webhook_url, json=event)
            except Exception as exc:
                log.warning("owner.notify.failed", error=str(exc))
