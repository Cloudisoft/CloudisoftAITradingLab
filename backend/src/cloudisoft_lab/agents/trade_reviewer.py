"""Trade Reviewer: post-trade analysis. Identifies where money was lost and proposes fixes."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from cloudisoft_lab.backtest.engine import Trade


def review(trades: Sequence[Trade]) -> dict[str, object]:
    closed = [t for t in trades if t.exit_price is not None]
    if not closed:
        return {"trades": 0, "findings": ["no closed trades to review"], "suggestions": []}
    gross = sum((t.exit_price - t.entry_price) * t.quantity for t in closed)  # type: ignore[operator]
    fees = sum(t.entry_fee + t.exit_fee for t in closed)
    reasons = Counter(t.exit_reason for t in closed)
    losers = [t for t in closed if t.pnl <= 0]
    hold = [(t.exit_time - t.entry_time).total_seconds() / 3600 for t in closed if t.exit_time is not None]
    streak = cur = 0
    for t in closed:
        cur = cur + 1 if t.pnl <= 0 else 0
        streak = max(streak, cur)
    findings, suggestions = [], []
    if gross > 0 and fees > 0.5 * gross:
        findings.append(f"fees consumed {fees / gross:.0%} of gross profit")
        suggestions.append("reduce trade frequency or require larger expected moves")
    if gross <= 0 < fees:
        findings.append("strategy loses before costs; costs only deepen losses")
        suggestions.append("pause strategy and research a different edge")
    if reasons.get("stop", 0) > 0.5 * len(closed):
        findings.append("majority of exits are stop-outs")
        suggestions.append("test wider stops or an entry trend filter (e.g. ADX > 20) in walk-forward")
    if streak >= 5:
        findings.append(f"longest losing streak: {streak}")
    return {
        "trades": len(closed), "win_rate": 1 - len(losers) / len(closed), "gross_pnl": gross, "fees": fees,
        "net_pnl": sum(t.pnl for t in closed), "exit_reasons": dict(reasons),
        "avg_holding_hours": sum(hold) / len(hold) if hold else 0, "max_losing_streak": streak,
        "findings": findings or ["no major issues detected"], "suggestions": suggestions,
        "label": "review of supplied trades",
    }
