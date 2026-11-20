"""Sentiment Analyst. Lexicon baseline (free, deterministic) with optional LLM refinement."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from cloudisoft_lab.ai.llm import LLMGateway
from cloudisoft_lab.domain.enums import SurvivalState

POSITIVE = set("""beat beats surge surges rally rallies gain gains record upgrade upgraded growth profit profits
bullish outperform strong soar soars jump jumps rise rises approval approved partnership expands expansion
dividend buyback recovery rebound tops raises raised""".split())
NEGATIVE = set("""miss misses plunge plunges fall falls drop drops loss losses downgrade downgraded bearish weak
lawsuit probe investigation fraud hack hacked exploit bankrupt bankruptcy default selloff sell-off slump
slumps cut cuts layoffs ban banned fine fined delist delisted recall warning warns crash crashes""".split())
NEGATORS = {"not", "no", "never", "without"}


class SentimentScore(BaseModel):
    score: float = Field(ge=-1, le=1, description="-1 very negative .. +1 very positive")
    label: Literal["negative", "neutral", "positive"]
    rationale: str = Field(max_length=400)


def lexicon_score(text: str) -> SentimentScore:
    words = re.findall(r"[a-z\-]+", text.lower())
    s = 0
    for i, w in enumerate(words):
        sign = 1 if w in POSITIVE else -1 if w in NEGATIVE else 0
        if sign and NEGATORS.intersection(words[max(0, i - 2):i]):
            sign = -sign
        s += sign
    score = max(-1.0, min(1.0, s / 3))
    label = "positive" if score > 0.15 else "negative" if score < -0.15 else "neutral"
    return SentimentScore(score=score, label=label, rationale="lexicon baseline")


async def analyse(text: str, llm: LLMGateway | None = None,
                  state: SurvivalState = SurvivalState.NORMAL) -> SentimentScore:
    if llm is not None and llm.available:
        out = await llm.structured(
            agent="sentiment_analyst", state=state, schema=SentimentScore, max_tokens=1000, effort="low",
            system="You rate the market sentiment of a single news item for the named asset. "
                   "Be calibrated; reply neutral when unclear. You never give investment advice.",
            prompt=text[:4000])
        if out is not None:
            return out
    return lexicon_score(text)
