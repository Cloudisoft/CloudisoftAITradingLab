"""Inference cost control: choose a model tier from the survival state and track spend."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from cloudisoft_lab.domain.enums import SurvivalState
from cloudisoft_lab.survival.engine import POLICIES

# Prices are per million tokens (input, output) in USD and MUST be refreshed from the
# provider's published price list before being used for real budgeting.
DEFAULT_MODEL_TIERS: dict[str, dict[str, object]] = {
    "premium": {"model": "claude-opus-5-5", "in": Decimal("5"), "out": Decimal("25")},
    "standard": {"model": "claude-sonnet-5-5", "in": Decimal("3"), "out": Decimal("15")},
    "economy": {"model": "claude-haiku-5-5", "in": Decimal("1"), "out": Decimal("5")},
}


@dataclass
class ModelRouter:
    tiers: dict[str, dict[str, object]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.tiers = self.tiers or DEFAULT_MODEL_TIERS

    def select(self, state: SurvivalState, essential: bool = False) -> str | None:
        tier = POLICIES[state].model_tier
        if tier == "none":
            return None
        if not essential and not POLICIES[state].run_non_essential_jobs:
            return None
        return str(self.tiers[tier]["model"])

    def cost(self, model: str, input_tokens: int, output_tokens: int) -> Decimal:
        for t in self.tiers.values():
            if t["model"] == model:
                return (Decimal(input_tokens) * t["in"] + Decimal(output_tokens) * t["out"]) / Decimal(1_000_000)  # type: ignore[operator]
        raise KeyError(model)
