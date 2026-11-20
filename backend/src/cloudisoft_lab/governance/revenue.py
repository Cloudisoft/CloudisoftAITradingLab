"""Legitimate revenue-opportunity research (non-trading income).

The module researches and drafts; it never sells, contacts people, signs contracts or counts
money. Estimates are ESTIMATED. Only an owner-recorded, received payment with a reference becomes
``external_revenue`` in the survival ledger.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

BANNED = [
    (r"guarantee[ds]?\s+(returns?|profits?|income)", "promising returns is prohibited"),
    (r"risk[- ]free", "claiming no risk is misleading"),
    (r"\b(buy|sell)\s+signals?\s+for\s+(clients|subscribers)", "selling trade signals may require SEBI RA/IA registration"),
    (r"investment advice|portfolio management service|\bpms\b", "advice/PMS requires SEBI registration"),
    (r"cold[- ]?(email|call|dm)|mass[- ]?(email|message)|scrap(e|ing) (emails|contacts)",
     "unsolicited outreach/spam is prohibited"),
    (r"(login|log in) (to|into) (client|customer|user) accounts?", "accessing others' accounts is prohibited"),
]

CHECKLIST = (
    "No promise or implication of returns",
    "No personalised investment advice unless the owner holds the required registration",
    "No unsolicited bulk outreach; opt-in marketing only",
    "Track records shown are verified and labelled (simulated vs actual)",
    "Customer data handled under applicable privacy law",
    "Owner signs any contract; agents never do",
)


@dataclass
class RevenueOpportunity:
    name: str
    description: str
    target_customers: str
    delivery_cost_monthly: Decimal  # ESTIMATED
    expected_revenue_monthly: Decimal  # ESTIMATED
    setup_cost: Decimal = Decimal(0)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "idea"  # idea | researching | proposed | approved | active | rejected
    created_at: str = field(default_factory=lambda: dt.datetime.now(dt.UTC).isoformat())
    compliance_issues: list[str] = field(default_factory=list)
    receipts: list[dict[str, str]] = field(default_factory=list)

    def score(self) -> dict[str, object]:
        margin = self.expected_revenue_monthly - self.delivery_cost_monthly
        payback = (self.setup_cost / margin) if margin > 0 else None
        return {"estimated_monthly_margin": str(margin), "payback_months": str(payback) if payback else None,
                "label": "ESTIMATED — not revenue until received"}


class RevenueComplianceError(ValueError):
    pass


def compliance_check(text: str) -> list[str]:
    t = text.lower()
    return [why for pat, why in BANNED if re.search(pat, t)]


SEED_IDEAS = [
    ("Quant research reports", "Periodic, clearly-labelled market structure & backtest research reports (education, not advice).",
     "retail learners, trading communities", "5", "0"),
    ("Data analysis service", "Custom data cleaning / backtesting-as-a-service on client-supplied data under contract.",
     "small funds, analysts, students", "10", "0"),
    ("Strategy analytics software",
     "Self-serve analytics: walk-forward, Monte Carlo and cost modelling for users' own strategies.",
     "independent quants", "20", "0"),
]


@dataclass
class RevenueDesk:
    items: dict[str, RevenueOpportunity] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.items:
            for n, d, c, cost, rev in SEED_IDEAS:
                self.add(RevenueOpportunity(n, d, c, Decimal(cost), Decimal(rev)))

    def add(self, o: RevenueOpportunity) -> RevenueOpportunity:
        issues = compliance_check(f"{o.name} {o.description} {o.target_customers}")
        if issues:
            raise RevenueComplianceError("; ".join(issues))
        self.items[o.id] = o
        return o

    def record_receipt(self, oid: str, amount: Decimal, reference: str, payer: str) -> dict[str, str]:
        o = self.items[oid]
        if o.status not in ("approved", "active"):
            raise RevenueComplianceError("revenue can only be recorded for an owner-approved opportunity")
        if amount <= 0 or not reference.strip():
            raise RevenueComplianceError("a positive amount and a payment reference are required")
        o.status = "active"
        rec = {"amount": str(amount), "reference": reference, "payer": payer, "at": dt.datetime.now(dt.UTC).isoformat()}
        o.receipts.append(rec)
        return rec
