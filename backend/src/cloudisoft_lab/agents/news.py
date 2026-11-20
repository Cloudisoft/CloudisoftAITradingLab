"""News Analyst: pulls items from owner-configured RSS/Atom feeds (permitted sources only),
matches them to watched symbols and scores sentiment. Failures are reported, never fatal."""

from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET  # noqa: S405 - parsed content is size-limited and not executed
from dataclasses import dataclass, field

import httpx

from cloudisoft_lab.agents.sentiment import SentimentScore, analyse
from cloudisoft_lab.ai.llm import LLMGateway
from cloudisoft_lab.domain.enums import SurvivalState

MAX_FEED_BYTES = 2_000_000


@dataclass
class NewsItem:
    title: str
    link: str
    source: str
    published: str | None = None
    symbols: list[str] = field(default_factory=list)
    sentiment: SentimentScore | None = None


def _child(node: ET.Element, name: str) -> ET.Element | None:
    return next((c for c in node if c.tag.split("}")[-1] == name), None)


def parse_feed(xml_text: str, source: str) -> list[NewsItem]:
    if len(xml_text) > MAX_FEED_BYTES or "<!ENTITY" in xml_text:
        raise ValueError("feed rejected (too large or contains entity declarations)")
    root = ET.fromstring(xml_text)  # noqa: S314
    items: list[NewsItem] = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = _child(it, "title")
        link = _child(it, "link")
        pub = next((c for c in (_child(it, n) for n in ("pubDate", "published", "updated")) if c is not None), None)
        href = (link.get("href") or link.text) if link is not None else ""
        items.append(NewsItem((title.text or "").strip() if title is not None else "", href or "", source,
                              pub.text if pub is not None else None))
    return items


ALIASES = {"BTCUSDT": ["bitcoin", "btc"], "ETHUSDT": ["ethereum", "eth", "ether"]}


def tag_symbols(items: list[NewsItem], symbols: list[str]) -> list[NewsItem]:
    for item in items:
        t = item.title.lower()
        item.symbols = [s for s in symbols if any(a in t.split() or a in t for a in ALIASES.get(s, [s.lower()]))]
    return items


@dataclass
class NewsAnalyst:
    feeds: list[str]
    llm: LLMGateway | None = None
    errors: list[str] = field(default_factory=list)
    last_run: str | None = None

    async def fetch(self, client: httpx.AsyncClient) -> list[NewsItem]:
        out: list[NewsItem] = []
        for url in self.feeds:
            try:
                r = await client.get(url, timeout=10, follow_redirects=True)
                r.raise_for_status()
                out.extend(parse_feed(r.text, httpx.URL(url).host))
            except Exception as exc:  # outage or malformed feed
                self.errors.append(f"{url}: {exc}")
        return out

    async def run(self, symbols: list[str], state: SurvivalState,
                  items: list[NewsItem] | None = None) -> list[NewsItem]:
        if items is None:
            async with httpx.AsyncClient(headers={"User-Agent": "cloudisoft-lab/0.1"}) as c:
                items = await self.fetch(c)
        tagged = [i for i in tag_symbols(items, symbols) if i.symbols]
        for i in tagged:
            # LLM only on relevant items; lexicon otherwise (and always in LOW_COMPUTE or worse)
            use_llm = self.llm if state in (SurvivalState.HIGH, SurvivalState.NORMAL, SurvivalState.PROFITABLE) else None
            i.sentiment = await analyse(f"Asset: {', '.join(i.symbols)}\nHeadline: {i.title}", use_llm, state)
        self.last_run = dt.datetime.now(dt.UTC).isoformat()
        return tagged


def aggregate(items: list[NewsItem]) -> dict[str, dict[str, float]]:
    agg: dict[str, list[float]] = {}
    for i in items:
        for s in i.symbols:
            if i.sentiment:
                agg.setdefault(s, []).append(i.sentiment.score)
    return {s: {"mean": sum(v) / len(v), "count": len(v)} for s, v in agg.items()}
