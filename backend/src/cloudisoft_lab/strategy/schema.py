"""Structured, versionable strategy definitions (what the visual builder / NL generator emit)."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from cloudisoft_lab.indicators import INDICATORS

Operator = Literal[">", "<", ">=", "<=", "crosses_above", "crosses_below"]


class Operand(BaseModel):
    indicator: str | None = None
    params: dict[str, float] = Field(default_factory=dict)
    value: float | None = None

    @model_validator(mode="after")
    def _one_of(self) -> Operand:
        if (self.indicator is None) == (self.value is None):
            raise ValueError("operand needs exactly one of indicator or value")
        if self.indicator is not None and self.indicator not in INDICATORS:
            raise ValueError(f"unknown indicator {self.indicator}")
        return self


class Condition(BaseModel):
    left: Operand
    op: Operator
    right: Operand


class ConditionGroup(BaseModel):
    logic: Literal["AND", "OR"] = "AND"
    conditions: list[Condition | ConditionGroup] = Field(min_length=1)


class RiskParams(BaseModel):
    stop_loss_pct: float | None = Field(default=0.03, gt=0, lt=0.5)
    take_profit_pct: float | None = Field(default=0.06, gt=0, lt=5)
    trailing_stop_pct: float | None = Field(default=None, gt=0, lt=0.5)
    position_fraction: float = Field(default=0.25, gt=0, le=1.0)
    max_holding_bars: int | None = Field(default=None, gt=0)


class StrategyDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    version: int = Field(default=1, ge=1)
    description: str = ""
    long_only: Literal[True] = True  # no shorting/leverage in the initial phase
    entry: ConditionGroup
    exit: ConditionGroup | None = None
    risk: RiskParams = Field(default_factory=RiskParams)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    def fingerprint(self) -> str:
        """Content hash: any modification yields a new fingerprint -> new version record."""
        body = self.model_dump(mode="json", exclude={"version"})
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]

    def bump(self, **changes: object) -> StrategyDefinition:
        data = self.model_dump()
        data.update(changes)
        data["version"] = self.version + 1
        return StrategyDefinition.model_validate(data)
