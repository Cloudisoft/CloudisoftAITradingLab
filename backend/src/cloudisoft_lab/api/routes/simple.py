"""Endpoints for the beginner-friendly app: markets, candles, one-tap trading, bot status, activity."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from cloudisoft_lab.agents.scanner import technical_snapshot
from cloudisoft_lab.api.deps import LabDep, Operator, persist
from cloudisoft_lab.domain.enums import Side
from cloudisoft_lab.explain import STATE_TEXT, coin_name, insights, reason
from cloudisoft_lab.worker.lab import Lab

router = APIRouter(prefix="/api")

LABEL = "Simulated prices for practice. Not the real market."
RULES = {"1h": "1h", "4h": "4h", "1d": "1D"}


async def _frame(lab: Lab, sym: str) -> pd.DataFrame:
    df = lab.frames.get(sym)
    if df is None:
        try:
            df = await lab.provider.get_candles(sym, lab.settings.paper_interval, 300)
        except Exception as exc:
            raise HTTPException(503, f"prices for {coin_name(sym)} are unavailable right now") from exc
        lab.frames[sym] = df
    if sym not in lab.paper.marks:
        lab.paper.mark(sym, Decimal(str(float(df["close"].iloc[-1]))))
    return df


def _change(df: pd.DataFrame, bars: int = 24) -> float | None:
    c = df["close"]
    return float(c.iloc[-1] / c.iloc[-bars - 1] - 1) if len(c) > bars else None


@router.get("/markets")
async def markets(lab: LabDep) -> dict[str, object]:
    rows = []
    for sym in lab.settings.paper_symbols:
        df = await _frame(lab, sym)
        pos = lab.paper.positions.get(sym)
        rows.append({
            "symbol": sym, "name": coin_name(sym), "price": float(df["close"].iloc[-1]),
            "change_24h": _change(df), "spark": [round(float(x), 6) for x in df["close"].iloc[-48:]],
            "holding_qty": str(pos.qty) if pos and pos.qty > 0 else None,
        })
    return {"label": LABEL, "markets": rows}


@router.get("/markets/{symbol}")
async def market_detail(symbol: str, lab: LabDep, tf: Literal["1h", "4h", "1d"] = "1h") -> dict[str, object]:
    if symbol not in lab.settings.paper_symbols:
        raise HTTPException(404, "coin not in your watchlist")
    df = await _frame(lab, symbol)
    if tf != "1h":
        df = df.resample(RULES[tf]).agg({"open": "first", "high": "max", "low": "min", "close": "last",
                                         "volume": "sum"}).dropna()
    raw = lab.frames[symbol]
    snap = technical_snapshot(raw)
    pos = lab.paper.positions.get(symbol)
    price = float(raw["close"].iloc[-1])
    holding = None
    if pos and pos.qty > 0:
        value = float(pos.qty) * price
        cost = float(pos.qty * pos.avg)
        holding = {"qty": str(pos.qty), "avg_price": float(pos.avg), "value": value, "pnl": value - cost,
                   "pnl_pct": (value / cost - 1) if cost else 0}
    candles = [{"time": int(ts.timestamp()), "open": float(r.open), "high": float(r.high), "low": float(r.low),
                "close": float(r.close), "volume": float(r.volume)} for ts, r in df.iterrows()]
    return {"label": LABEL, "symbol": symbol, "name": coin_name(symbol), "price": price,
            "change_24h": _change(raw), "high_24h": float(raw["high"].iloc[-24:].max()),
            "low_24h": float(raw["low"].iloc[-24:].min()), "candles": candles, "insights": insights(snap),
            "holding": holding, "available_cash": float(lab.paper.cash)}


class TradeBody(BaseModel):
    symbol: str
    side: Side
    amount_usd: Decimal | None = Field(default=None, gt=0, le=Decimal(1_000_000))
    sell_all: bool = False


async def _trade(body: TradeBody, lab: Lab, user: dict[str, str], preview: bool) -> dict[str, object]:
    if body.symbol not in lab.settings.paper_symbols:
        raise HTTPException(404, "coin not in your watchlist")
    try:
        out = await lab.manual_trade(body.symbol, body.side, body.amount_usd, body.sell_all,
                                     f"owner:{user['sub']}", preview=preview)
    except ValueError as exc:
        raise HTTPException(422, str(exc)[:1].upper() + str(exc)[1:]) from exc
    out["friendly_reasons"] = [reason(r) for r in out.get("reasons", [])]  # type: ignore[union-attr]
    out["name"] = coin_name(body.symbol)
    return out


@router.post("/trade/preview")
async def trade_preview(body: TradeBody, lab: LabDep, user: Operator) -> dict[str, object]:
    return await _trade(body, lab, user, preview=True)


@router.post("/trade")
async def trade(body: TradeBody, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    out = await _trade(body, lab, user, preview=False)
    lab.audit.record("trade.manual", user["sub"], {k: str(v) for k, v in out.items()})
    await persist(request)
    return out


@router.get("/bot")
async def bot(lab: LabDep) -> dict[str, object]:
    r = lab.survival_report()
    rec = lab.strategies.active()
    p = lab.paper
    holding = [coin_name(s) for s, x in p.positions.items() if x.qty > 0]
    last = next((o for o in reversed(list(p.orders.values()))
                 if o.status == "filled"), None)
    min_order = Decimal(5)
    per_trade = p.cash * Decimal(str(lab.active_strategy().risk.position_fraction))
    if lab.kill_switch:
        headline = "Your bot is stopped by the emergency switch."
    elif not lab.bot_enabled:
        headline = "Your bot is paused. It will keep watching but won't buy."
    elif r.state in ("CRITICAL", "DEAD"):
        headline = "Your bot has stopped buying to protect your budget."
    elif per_trade < min_order and not holding:
        headline = (f"Your bot is watching {len(lab.settings.paper_symbols)} coins, but ${per_trade:.2f} per trade "
                    f"is below the $5 minimum. Add practice money to let it trade.")
    elif holding:
        headline = f"Your bot is holding {', '.join(holding)} and watching for the right time to sell."
    else:
        headline = f"Your bot is watching {len(lab.settings.paper_symbols)} coins and waiting for a good moment to buy."
    return {
        "headline": headline, "enabled": lab.bot_enabled and not lab.kill_switch, "paused": not lab.bot_enabled,
        "kill_switch": lab.kill_switch, "health": STATE_TEXT.get(r.state, r.state), "state": r.state,
        "strategy": rec.name if rec else None,
        "strategy_plain": "Buys when a coin starts trending up and the move is strong; sells when the trend turns, "
                          "or at a 3% loss / 8% gain." if rec and "EMA" in rec.name else None,
        "checks_every_minutes": round(
            lab.settings.paper_loop_seconds * (lab.survival.policy.scan_interval_multiplier or 12) / 60),
        "last_trade": {"side": last.side, "name": coin_name(last.symbol), "price": str(last.average_price),
                       "qty": str(last.filled_quantity)} if last else None,
        "per_trade_usd": float(per_trade), "practice_money": True,
    }


class BotToggle(BaseModel):
    enabled: bool


@router.post("/bot")
async def bot_toggle(body: BotToggle, lab: LabDep, user: Operator, request: Request) -> dict[str, bool]:
    lab.bot_enabled = body.enabled
    lab.audit.record("bot.toggled", user["sub"], {"enabled": body.enabled})
    await persist(request)
    return {"enabled": lab.bot_enabled}


@router.get("/activity")
async def activity(lab: LabDep, limit: int = 50) -> dict[str, object]:
    items = []
    for o in reversed(list(lab.paper.orders.values())[-limit:]):
        items.append({"kind": "order", "status": o.status, "side": o.side, "name": coin_name(o.symbol),
                      "symbol": o.symbol, "qty": str(o.filled_quantity or o.requested_quantity),
                      "price": str(o.average_price) if o.average_price else None, "fees": str(o.fees),
                      "reason": reason(o.reason) if o.reason else None, "ref": o.provider_reference})
    return {"label": "Practice trades (simulated)", "items": items}
