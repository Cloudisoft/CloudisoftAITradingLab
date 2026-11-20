"""AI Quant Research, Market Data, Portfolio analysis endpoints."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from cloudisoft_lab.agents import fundamental, portfolio, sentiment
from cloudisoft_lab.agents.news import NewsItem, aggregate
from cloudisoft_lab.agents.trade_reviewer import review
from cloudisoft_lab.api.deps import LabDep, Operator, Owner, persist
from cloudisoft_lab.backtest.engine import CostModel, run_backtest
from cloudisoft_lab.data.synthetic import make_ohlcv

router = APIRouter(prefix="/api/research")


class TextBody(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/sentiment")
async def sentiment_ep(body: TextBody, lab: LabDep, user: Operator) -> dict[str, object]:
    r = await sentiment.analyse(body.text, lab.llm, lab.survival.state)
    return r.model_dump()


class HeadlinesBody(BaseModel):
    headlines: list[str] = Field(default_factory=list, max_length=200)


@router.post("/news")
async def news_ep(body: HeadlinesBody, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    """Score supplied headlines, or (if none supplied) fetch the owner-configured feeds."""
    items = [NewsItem(h, "", "owner_supplied") for h in body.headlines] if body.headlines else None
    if items is None and not lab.news_analyst.feeds:
        raise HTTPException(422, "no headlines supplied and no feeds configured (CLAB_NEWS_FEEDS)")
    out = await lab.news_analyst.run(lab.settings.paper_symbols, lab.survival.state, items)
    lab.news = [{"title": i.title, "link": i.link, "source": i.source, "symbols": i.symbols,
                 "sentiment": i.sentiment.model_dump() if i.sentiment else None} for i in out]
    lab.agents.log_task("news_analyst", "news_scan", "ok", items=len(out))
    await persist(request)
    return {"items": lab.news, "aggregate": aggregate(out), "errors": lab.news_analyst.errors[-10:]}


@router.post("/fundamentals")
async def fundamentals_ep(body: fundamental.Fundamentals, user: Operator) -> dict[str, object]:
    return fundamental.score(body).model_dump()


@router.get("/portfolio")
async def portfolio_ep(lab: LabDep) -> dict[str, object]:
    p = lab.paper
    return {"label": "simulated", **portfolio.analyse({s: x.qty for s, x in p.positions.items()}, p.marks, p.cash)}


class ReviewBody(BaseModel):
    regime: str = "volatile"
    bars: int = Field(default=2000, ge=200, le=20000)
    seed: int = 1


@router.post("/trade-review")
async def trade_review_ep(body: ReviewBody, lab: LabDep, user: Operator) -> dict[str, object]:
    """Review trades of the ACTIVE strategy on a backtest (paper fills are reviewed via /api/reports)."""
    df = make_ohlcv(body.bars, body.regime, seed=body.seed)
    r = run_backtest(df, lab.active_strategy(), 1000, CostModel(min_notional=0))
    lab.agents.log_task("trade_reviewer", "review", "ok", trades=len(r.trades))
    return {"label": "SIMULATED backtest trades", **review(r.trades)}


class DatasetBody(BaseModel):
    symbol: str = Field(pattern=r"^[A-Z0-9_\-\.]{2,32}$")
    csv: str = Field(min_length=10, max_length=60_000_000)
    source: str = Field(min_length=2, max_length=200, description="where the data came from")
    owner_asserts_real: bool = False


@router.post("/datasets")
async def upload_dataset(body: DatasetBody, lab: LabDep, user: Owner) -> dict[str, object]:
    try:
        q = lab.datasets.add(body.symbol, body.csv, body.source, body.owner_asserts_real)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, f"invalid CSV: {exc}") from exc
    lab.audit.record("dataset.upload", user["sub"], {"symbol": body.symbol, "ok": q.ok, "issues": q.issues})
    if not q.ok:
        raise HTTPException(422, {"issues": q.issues})
    return {"ok": True, "datasets": lab.datasets.summary()}


@router.get("/datasets")
async def list_datasets(lab: LabDep) -> dict[str, object]:
    return {"datasets": lab.datasets.summary()}


@router.get("/llm")
async def llm_usage(lab: LabDep) -> dict[str, object]:
    llm = lab.llm
    return {"available": bool(llm and llm.available),
            "note": None if llm and llm.available else "No Anthropic credentials: agents use rule-based fallbacks.",
            "budgets": {k: {"limit": str(b.limit_usd), "spent": str(b.spent_usd)}
                        for k, b in (llm.budgets if llm else {}).items()},
            "calls": (llm.calls[-100:] if llm else [])}


def _equity_returns(lab: LabDep) -> pd.Series:
    return pd.Series([v for _, v in lab.equity_curve]).pct_change().dropna()


__all__ = ["Decimal"]
