"""Budget-aware LLM gateway for research agents.

* Model tier comes from the survival state (``ModelRouter``); in DEAD/CRITICAL non-essential calls are refused.
* Each agent has its own budget; a call that would exceed it is refused before it is sent.
* Every billed call is written to the survival ledger as ``ai_inference_cost`` (ACTUAL) with the agent id.
* Output is schema-validated (structured outputs via ``messages.parse``); a refusal returns ``None``.
* Without credentials the gateway is ``available == False`` and agents use their rule-based fallbacks.
"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from cloudisoft_lab.core.logging import get_logger
from cloudisoft_lab.core.money import ZERO
from cloudisoft_lab.domain.enums import DataOrigin, SurvivalState
from cloudisoft_lab.survival.ledger import Entry, SurvivalLedger
from cloudisoft_lab.survival.model_router import ModelRouter

log = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMBackend(Protocol):
    async def parse(self, *, model: str, system: str, prompt: str, schema: type[T],
                    max_tokens: int, effort: str) -> tuple[T | None, str, int, int]:
        """Return (parsed | None on refusal, model_that_served, input_tokens, output_tokens)."""
        ...


class AnthropicBackend:
    def __init__(self) -> None:
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.AsyncAnthropic(max_retries=2, timeout=120)

    async def parse(self, *, model: str, system: str, prompt: str, schema: type[T],
                    max_tokens: int, effort: str) -> tuple[T | None, str, int, int]:
        kwargs: dict[str, Any] = {}
        if not model.startswith("claude-haiku"):  # Haiku has no server-side refusal fallback
            kwargs = {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        resp = await self.client.beta.messages.parse(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema, output_config={"effort": effort}, **kwargs,
        )
        usage = resp.usage
        if resp.stop_reason == "refusal":
            return None, resp.model, usage.input_tokens, usage.output_tokens
        return resp.parsed_output, resp.model, usage.input_tokens, usage.output_tokens


def credentials_present() -> bool:
    return any(os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"))


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class AgentBudget:
    limit_usd: Decimal
    spent_usd: Decimal = ZERO

    @property
    def remaining(self) -> Decimal:
        return self.limit_usd - self.spent_usd


@dataclass
class LLMGateway:
    ledger: SurvivalLedger
    backend: LLMBackend | None = None
    router: ModelRouter = field(default_factory=ModelRouter)
    budgets: dict[str, AgentBudget] = field(default_factory=dict)
    default_budget_usd: Decimal = Decimal("1.00")
    calls: list[dict[str, object]] = field(default_factory=list)

    @classmethod
    def from_env(cls, ledger: SurvivalLedger) -> LLMGateway:
        return cls(ledger, AnthropicBackend() if credentials_present() else None)

    @property
    def available(self) -> bool:
        return self.backend is not None

    def budget(self, agent: str) -> AgentBudget:
        return self.budgets.setdefault(agent, AgentBudget(self.default_budget_usd))

    async def structured(self, *, agent: str, state: SurvivalState, system: str, prompt: str,
                         schema: type[T], essential: bool = False, max_tokens: int = 8000,
                         effort: str = "medium") -> T | None:
        if self.backend is None:
            return None
        model = self.router.select(state, essential=essential)
        if model is None:
            log.info("llm.skipped", agent=agent, state=state)
            return None
        b = self.budget(agent)
        worst_case = self.router.cost(model, len(prompt) // 3 + len(system) // 3, max_tokens)
        if worst_case > b.remaining:
            raise BudgetExceeded(f"{agent}: worst-case ${worst_case:.4f} exceeds remaining ${b.remaining:.4f}")
        parsed, served, tin, tout = await self.backend.parse(
            model=model, system=system, prompt=prompt, schema=schema, max_tokens=max_tokens, effort=effort)
        try:
            cost = self.router.cost(served, tin, tout)
        except KeyError:  # fallback model outside our tiers: price at premium (conservative)
            cost = self.router.cost(str(self.router.tiers["premium"]["model"]), tin, tout)
        b.spent_usd += cost
        self.ledger.add(Entry.AI_INFERENCE_COST, cost, origin=DataOrigin.ACTUAL, agent_id=agent,
                        memo=f"{served} in={tin} out={tout}")
        self.calls.append({"at": dt.datetime.now(dt.UTC).isoformat(), "agent": agent, "model": served,
                           "input_tokens": tin, "output_tokens": tout, "cost_usd": str(cost),
                           "refused": parsed is None})
        return parsed
