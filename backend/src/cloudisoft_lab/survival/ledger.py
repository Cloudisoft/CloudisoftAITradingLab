"""Survival ledger: the single source of truth for the agent's economics.

Accounting rules (see SURVIVAL_ENGINE_SPEC.md):
* Owner deposits are FUNDING, never revenue.
* Only REALISED trading P&L counts; unrealised gains are excluded.
* Trading capital and operating budget are separate buckets. Money moves between them only
  through explicit owner-approved ``allocate`` entries, so nothing is double counted.
* External revenue counts only when ``verified`` (actually received) is true.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from cloudisoft_lab.core.money import ZERO
from cloudisoft_lab.domain.enums import DataOrigin


class Entry(StrEnum):
    OWNER_FUNDING_TRADING = "owner_funding_trading"
    OWNER_FUNDING_OPERATIONS = "owner_funding_operations"
    REALISED_TRADING_PNL = "realised_trading_pnl"  # gross of fees
    TRADING_FEE = "trading_fee"
    EXECUTION_COST = "execution_cost"
    AI_INFERENCE_COST = "ai_inference_cost"
    HOSTING_COST = "hosting_cost"
    DATA_COST = "data_cost"
    OTHER_EXPENSE = "other_expense"
    EXTERNAL_REVENUE = "external_revenue"
    OWNER_WITHDRAWAL = "owner_withdrawal"


EXPENSES = {Entry.AI_INFERENCE_COST, Entry.HOSTING_COST, Entry.DATA_COST, Entry.OTHER_EXPENSE}


@dataclass(frozen=True)
class LedgerEntry:
    kind: Entry
    amount: Decimal  # always positive; sign implied by kind (except PnL, which is signed)
    origin: DataOrigin
    at: dt.datetime
    memo: str = ""
    agent_id: str | None = None
    strategy_id: str | None = None
    verified: bool = True
    reference: str | None = None


@dataclass
class SurvivalLedger:
    entries: list[LedgerEntry] = field(default_factory=list)
    #: share of positive net trading profit that may be counted toward operations
    earnings_to_operations_fraction: Decimal = Decimal("0.5")
    #: if True, SIMULATED trading P&L is ignored for survival (real economics only)
    count_simulated_pnl: bool = False

    def add(self, kind: Entry, amount: Decimal, origin: DataOrigin = DataOrigin.ACTUAL,
            at: dt.datetime | None = None, **kw: object) -> LedgerEntry:
        if kind != Entry.REALISED_TRADING_PNL and amount < 0:
            raise ValueError(f"{kind} amounts must be non-negative")
        if kind == Entry.EXTERNAL_REVENUE and origin != DataOrigin.ACTUAL:
            raise ValueError("external revenue must be an ACTUAL received amount")
        e = LedgerEntry(kind, amount, origin, at or dt.datetime.now(dt.UTC), **kw)  # type: ignore[arg-type]
        self.entries.append(e)
        return e

    # ------------------------------------------------------------------
    def _sum(self, kinds: set[Entry] | Entry, since: dt.datetime | None = None,
             until: dt.datetime | None = None) -> Decimal:
        ks = {kinds} if isinstance(kinds, Entry) else kinds
        total = ZERO
        for e in self.entries:
            if e.kind not in ks or (since and e.at < since) or (until and e.at >= until):
                continue
            if e.kind in (Entry.REALISED_TRADING_PNL, Entry.TRADING_FEE, Entry.EXECUTION_COST) \
                    and e.origin == DataOrigin.SIMULATED and not self.count_simulated_pnl:
                continue
            if e.kind == Entry.EXTERNAL_REVENUE and not e.verified:
                continue
            total += e.amount
        return total

    def summary(self, since: dt.datetime | None = None, until: dt.datetime | None = None) -> dict[str, Decimal]:
        s = lambda k: self._sum(k, since, until)  # noqa: E731
        realised = s(Entry.REALISED_TRADING_PNL)
        fees = s(Entry.TRADING_FEE)
        exec_cost = s(Entry.EXECUTION_COST)
        ai, host, data, other = (s(Entry.AI_INFERENCE_COST), s(Entry.HOSTING_COST),
                                 s(Entry.DATA_COST), s(Entry.OTHER_EXPENSE))
        revenue = s(Entry.EXTERNAL_REVENUE)
        net_trading = realised - fees - exec_cost
        net_operating = net_trading + revenue - ai - host - data - other
        op_budget = s(Entry.OWNER_FUNDING_OPERATIONS)
        eligible = max(net_trading, ZERO) * self.earnings_to_operations_fraction + revenue
        expenses = ai + host + data + other
        survival_balance = op_budget + eligible - expenses
        trading_capital = s(Entry.OWNER_FUNDING_TRADING) + net_trading \
            - max(net_trading, ZERO) * self.earnings_to_operations_fraction - s(Entry.OWNER_WITHDRAWAL)
        return {
            "owner_funding_trading": s(Entry.OWNER_FUNDING_TRADING),
            "owner_funding_operations": op_budget,
            "realised_trading_pnl": realised,
            "trading_fees": fees,
            "execution_costs": exec_cost,
            "net_trading_profit": net_trading,
            "verified_external_revenue": revenue,
            "ai_costs": ai, "hosting_costs": host, "data_costs": data, "other_expenses": other,
            "operating_expenses": expenses,
            "net_operating_profit": net_operating,
            "eligible_realised_earnings": eligible,
            "survival_balance": survival_balance,
            "trading_capital": trading_capital,
        }

    def cost_by(self, attr: str) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for e in self.entries:
            if e.kind in EXPENSES:
                key = getattr(e, attr) or "unattributed"
                out[key] = out.get(key, ZERO) + e.amount
        return out

    def daily_burn(self, now: dt.datetime, days: int = 7) -> Decimal:
        since = now - dt.timedelta(days=days)
        spent = self._sum(EXPENSES, since, now)
        return spent / days
