"""Plain-English explanations for non-expert users. No jargon without a translation."""

from __future__ import annotations

COIN_NAMES = {"BTCUSDT": "Bitcoin", "ETHUSDT": "Ethereum", "SOLUSDT": "Solana", "BNBUSDT": "BNB"}


def coin_name(symbol: str) -> str:
    return COIN_NAMES.get(symbol, symbol.removesuffix("USDT"))


def insights(s: dict[str, float | None]) -> list[dict[str, str]]:
    """Turn an indicator snapshot into short sentences with a tone: up | down | neutral | caution."""
    out: list[dict[str, str]] = []
    c, ema20, ema50, sma200 = s.get("close"), s.get("ema20"), s.get("ema50"), s.get("sma200")
    if c and ema20 and ema50:
        if c > ema20 > ema50:
            out.append({"tone": "up", "text": "Price is climbing: it is above its recent averages."})
        elif c < ema20 < ema50:
            out.append({"tone": "down", "text": "Price is falling: it is below its recent averages."})
        else:
            out.append({"tone": "neutral", "text": "No clear direction right now."})
    if c and sma200:
        out.append({"tone": "up" if c > sma200 else "down",
                    "text": f"Long-term trend is {'up' if c > sma200 else 'down'} (compared with the last ~200 hours)."})
    rsi = s.get("rsi14")
    if rsi is not None:
        if rsi > 70:
            out.append({"tone": "caution",
                        "text": f"Bought heavily lately (strength {rsi:.0f}/100). Prices often cool off after this."})
        elif rsi < 30:
            out.append({"tone": "caution",
                        "text": f"Sold heavily lately (strength {rsi:.0f}/100). Prices sometimes bounce after this."})
        else:
            out.append({"tone": "neutral", "text": f"Buying and selling are balanced (strength {rsi:.0f}/100)."})
    adx = s.get("adx14")
    if adx is not None and adx > 25:
        out.append({"tone": "neutral", "text": "The current move is strong."})
    atr, close = s.get("atr14"), s.get("close")
    if atr and close and atr / close > 0.03:
        out.append({"tone": "caution", "text": "Very jumpy: prices are swinging a lot hour to hour."})
    vz = s.get("volume_z")
    if vz is not None and vz > 3:
        out.append({"tone": "caution", "text": "Unusually high trading activity right now."})
    return out


REASONS = [
    ("kill switch", "Trading is paused by the emergency stop."),
    ("survival state", "Paused to protect your money: the operating budget is running low."),
    ("insufficient funds", "Not enough practice money for this order."),
    ("below exchange minimum", "This order is too small. The minimum order size is $5."),
    ("uneconomical", "Fees would eat too much of this trade. Try a larger amount."),
    ("exceed max exposure", "This would put too much of your money in one coin (max 50%)."),
    ("too many open positions", "You already hold the maximum number of coins."),
    ("daily loss limit", "Today's loss limit is reached. New buys resume tomorrow."),
    ("martingale", "After a loss, the next buy can't be bigger than the last one."),
    ("short selling", "You can only sell coins you own."),
    ("market closed", "This market is closed right now."),
    ("max notional", "Order is larger than the per-order limit."),
    ("not a multiple of step", "Amount doesn't fit the coin's smallest unit."),
    ("live trading gates", "Real-money trading is switched off."),
]


def reason(text: str) -> str:
    t = text.lower()
    for key, friendly in REASONS:
        if key in t:
            return friendly
    return text[:1].upper() + text[1:]


STATE_TEXT = {
    "HIGH": "Healthy: plenty of budget to keep running.",
    "NORMAL": "Running normally.",
    "LOW_COMPUTE": "Saving money: checking less often and using cheaper AI.",
    "CRITICAL": "Budget nearly used up: not opening new trades.",
    "DEAD": "Stopped: budget used up. Waiting for you.",
    "PROFITABLE": "Earning more than it costs to run.",
}
