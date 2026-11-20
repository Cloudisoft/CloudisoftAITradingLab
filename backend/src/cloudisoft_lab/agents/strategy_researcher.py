"""Strategy Researcher: natural language -> validated StrategyDefinition.

Two paths, same output contract:
1. Deterministic parser for common phrasings (free, always available).
2. LLM with a flat structured-output schema (when credentials + survival state allow).
Every generated strategy is validated by the pydantic schema and immediately backtested with
costs; it starts life in ``research`` status and can never trade until promoted by the owner.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from cloudisoft_lab.ai.llm import LLMGateway
from cloudisoft_lab.domain.enums import SurvivalState
from cloudisoft_lab.indicators import INDICATORS
from cloudisoft_lab.strategy.schema import StrategyDefinition

Op = Literal[">", "<", ">=", "<=", "crosses_above", "crosses_below"]


class FlatOperand(BaseModel):
    indicator: str | None = Field(default=None, description=f"one of: {', '.join(INDICATORS)}")
    period: int | None = None
    value: float | None = None


class FlatCondition(BaseModel):
    left: FlatOperand
    op: Op
    right: FlatOperand


class FlatStrategy(BaseModel):
    name: str
    description: str
    entry_logic: Literal["AND", "OR"]
    entry: list[FlatCondition]
    exit_logic: Literal["AND", "OR"]
    exit: list[FlatCondition]
    stop_loss_pct: float | None
    take_profit_pct: float | None
    trailing_stop_pct: float | None
    position_fraction: float
    unsupported_requests: list[str] = Field(description="parts of the request that cannot be expressed")


def _op(o: FlatOperand) -> dict[str, object]:
    if o.indicator:
        return {"indicator": o.indicator, "params": {"period": o.period} if o.period else {}}
    return {"value": o.value}


def flat_to_definition(f: FlatStrategy) -> StrategyDefinition:
    conv = lambda cs: [{"left": _op(c.left), "op": c.op, "right": _op(c.right)} for c in cs]  # noqa: E731
    return StrategyDefinition.model_validate({
        "name": f.name[:80], "description": f.description,
        "entry": {"logic": f.entry_logic, "conditions": conv(f.entry)},
        "exit": {"logic": f.exit_logic, "conditions": conv(f.exit)} if f.exit else None,
        "risk": {"stop_loss_pct": f.stop_loss_pct, "take_profit_pct": f.take_profit_pct,
                 "trailing_stop_pct": f.trailing_stop_pct, "position_fraction": min(max(f.position_fraction, 0.01), 1)},
    })


_NUM = r"(\d+(?:\.\d+)?)"
_IND = r"(rsi|ema|sma|adx|atr|vwap|close|price|macd)"


def _operand(name: str, period: str | None) -> dict[str, object]:
    name = "close" if name == "price" else name
    return {"indicator": name, "params": {"period": float(period)} if period else {}}


def _parse_clause(text: str) -> list[dict[str, object]]:
    conds: list[dict[str, object]] = []
    for m in re.finditer(rf"{_IND}\s*\(?(\d+)?\)?\s*(crosses above|crosses below|above|below|over|under|>|<)\s*"
                         rf"(?:{_IND}\s*\(?(\d+)?\)?|{_NUM})", text):
        a, ap, rel, b, bp, num = m.groups()
        op = {"crosses above": "crosses_above", "crosses below": "crosses_below", "above": ">", "over": ">",
              ">": ">", "below": "<", "under": "<", "<": "<"}[rel]
        right = _operand(b, bp) if b else {"value": float(num)}
        conds.append({"left": _operand(a, ap), "op": op, "right": right})
    return conds


def parse_natural_language(text: str) -> StrategyDefinition:
    t = text.lower()
    parts = re.split(r"\b(?:sell|exit|close (?:the )?position)\b", t, maxsplit=1)
    entry_txt = parts[0]
    exit_txt = parts[1] if len(parts) > 1 else ""
    entry = _parse_clause(entry_txt)
    if not entry:
        raise ValueError("could not find an entry rule (e.g. 'buy when RSI 14 below 30')")
    exit_ = _parse_clause(exit_txt)
    pct = lambda k: (float(m.group(1)) / 100 if (m := re.search(k + r"\D{0,15}?" + _NUM + r"\s*%", t)) else None)  # noqa: E731
    size = pct(r"(?:position|size|allocate|risk)")
    return StrategyDefinition.model_validate({
        "name": text.strip()[:60] or "NL strategy", "description": f"Parsed from: {text.strip()[:500]}",
        "entry": {"logic": "OR" if " or " in entry_txt else "AND", "conditions": entry},
        "exit": {"logic": "OR" if " or " in exit_txt else "AND", "conditions": exit_} if exit_ else None,
        "risk": {"stop_loss_pct": pct("stop") or 0.03, "take_profit_pct": pct(r"(?:take profit|target)") or 0.06,
                 "trailing_stop_pct": pct("trailing"), "position_fraction": size or 0.25},
    })


SYSTEM = (
    "You translate a trader's description into a long-only, unleveraged rule-based strategy using only the "
    f"listed indicators ({', '.join(INDICATORS)}). Never invent indicators; list anything you cannot express "
    "in unsupported_requests. Percentages are fractions (3% -> 0.03). position_fraction is the share of "
    "available cash per trade (0-1). Do not promise returns."
)


async def generate(text: str, llm: LLMGateway | None, state: SurvivalState) -> tuple[StrategyDefinition, dict[str, object]]:
    meta: dict[str, object] = {"source": "parser", "unsupported": []}
    if llm is not None and llm.available:
        flat = await llm.structured(agent="strategy_researcher", state=state, schema=FlatStrategy,
                                    system=SYSTEM, prompt=text[:4000], effort="medium")
        if flat is not None:
            try:
                return flat_to_definition(flat), {"source": "llm", "unsupported": flat.unsupported_requests}
            except ValueError as exc:
                meta["llm_error"] = str(exc)
    return parse_natural_language(text), meta
