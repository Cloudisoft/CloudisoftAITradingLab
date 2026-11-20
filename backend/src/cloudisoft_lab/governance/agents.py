"""Agent registry: each agent has an isolated budget, task scope, task log and performance ledger.
New agents are created ONLY from an approved AGENT_SPAWN proposal, up to a hard cap."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from cloudisoft_lab.governance.proposals import GovernanceError, Proposal, ProposalKind, ProposalStatus

MAX_AGENTS = 20  # hard cap regardless of approvals (no runaway replication)

BUILTIN = {
    "market_scanner": ("Market Scanner", "scan watched markets; emit analysis only", "0"),
    "technical_analyst": ("Technical Analyst", "indicator snapshots", "0"),
    "news_analyst": ("News Analyst", "permitted RSS feeds; sentiment", "0.50"),
    "sentiment_analyst": ("Sentiment Analyst", "score text sentiment", "0.50"),
    "fundamental_analyst": ("Fundamental Analyst", "score owner-supplied fundamentals", "0"),
    "strategy_researcher": ("Strategy Researcher", "NL->strategy; backtests", "1.00"),
    "portfolio_analyst": ("Portfolio Analyst", "allocation, concentration, correlation", "0"),
    "risk_manager": ("Risk Manager", "independently validates every order", "0"),
    "execution_manager": ("Execution Manager", "routes risk-approved orders only", "0"),
    "trade_reviewer": ("Trade Reviewer", "post-trade analysis", "0"),
    "profit_manager": ("AI Profit Manager", "profit, withdrawal recommendations", "0"),
    "survival_manager": ("AI Survival Manager", "survival state & cost control", "0"),
    "improvement_researcher": ("Improvement Researcher", "propose tested strategy changes", "0.50"),
}


@dataclass
class AgentInfo:
    agent_id: str
    name: str
    scope: str
    budget_usd: Decimal
    status: str = "active"
    builtin: bool = True
    approved_by: str | None = None
    tasks: list[dict[str, object]] = field(default_factory=list)
    performance: dict[str, float] = field(default_factory=dict)


@dataclass
class AgentRegistry:
    agents: dict[str, AgentInfo] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for aid, (name, scope, budget) in BUILTIN.items():
            self.agents.setdefault(aid, AgentInfo(aid, name, scope, Decimal(budget)))

    def log_task(self, agent_id: str, kind: str, status: str, cost: Decimal = Decimal(0), **info: object) -> None:
        a = self.agents[agent_id]
        a.tasks.append({"at": dt.datetime.now(dt.UTC).isoformat(), "kind": kind, "status": status,
                        "cost_usd": str(cost), **info})
        a.tasks = a.tasks[-200:]

    def spawn_from(self, p: Proposal) -> AgentInfo:
        if p.kind != ProposalKind.AGENT_SPAWN or p.status != ProposalStatus.APPROVED:
            raise GovernanceError("agents can only be created from an approved AGENT_SPAWN proposal")
        if len(self.agents) >= MAX_AGENTS:
            raise GovernanceError(f"agent cap {MAX_AGENTS} reached")
        aid = str(p.payload["agent_id"])
        if aid in self.agents:
            raise GovernanceError("agent id already exists")
        info = AgentInfo(aid, str(p.payload.get("name", aid)), str(p.payload.get("scope", "")),
                         Decimal(str(p.payload.get("budget_usd", "0"))), builtin=False, approved_by=p.decided_by)
        self.agents[aid] = info
        return info

    def set_status(self, agent_id: str, status: str) -> AgentInfo:
        if status not in ("active", "paused", "retired"):
            raise ValueError("invalid status")
        self.agents[agent_id].status = status
        return self.agents[agent_id]
