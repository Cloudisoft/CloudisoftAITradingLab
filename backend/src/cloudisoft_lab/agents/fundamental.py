"""Fundamental Analyst: transparent rule-based scoring of owner-supplied company metrics.
Output is research, not a recommendation to buy or sell."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Fundamentals(BaseModel):
    symbol: str
    pe: float | None = None
    pb: float | None = None
    roe: float | None = Field(default=None, description="fraction, e.g. 0.18")
    debt_to_equity: float | None = None
    revenue_growth: float | None = None
    eps_growth: float | None = None
    dividend_yield: float | None = None
    sector_pe: float | None = None


class FundamentalReport(BaseModel):
    symbol: str
    score: float  # 0..100
    factors: dict[str, str]
    data_coverage: float
    label: str = "research only — not investment advice"


def score(f: Fundamentals) -> FundamentalReport:
    pts, maxpts, notes = 0.0, 0.0, {}

    def add(name: str, value: float | None, good: bool | None, w: float, msg: str) -> None:
        nonlocal pts, maxpts
        if value is None or good is None:
            notes[name] = "no data"
            return
        maxpts += w
        pts += w if good else 0
        notes[name] = f"{'+' if good else '-'} {msg} ({value:.3g})"

    pe_ref = f.sector_pe or 25
    add("valuation_pe", f.pe, None if f.pe is None else 0 < f.pe < pe_ref, 20, f"P/E vs reference {pe_ref}")
    add("price_to_book", f.pb, None if f.pb is None else 0 < f.pb < 5, 10, "P/B below 5")
    add("roe", f.roe, None if f.roe is None else f.roe >= 0.15, 20, "ROE ≥ 15%")
    add("leverage", f.debt_to_equity, None if f.debt_to_equity is None else f.debt_to_equity <= 1, 20, "D/E ≤ 1")
    rg = f.revenue_growth
    add("revenue_growth", rg, None if rg is None else rg > 0.08, 15, "revenue growth > 8%")
    add("eps_growth", f.eps_growth, None if f.eps_growth is None else f.eps_growth > 0.08, 15, "EPS growth > 8%")
    coverage = maxpts / 100
    return FundamentalReport(symbol=f.symbol, score=round(100 * pts / maxpts, 1) if maxpts else 0.0,
                             factors=notes, data_coverage=round(coverage, 2))
