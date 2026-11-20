# Repository Research & Integration Compatibility — Milestone 2

Method: each repository was shallow-fetched from its official GitHub URL on 2026-11-20 (metadata only,
no code executed). License text read from the repository's own LICENSE file; "last commit" is the
default-branch HEAD date; "latest tag" from `git ls-remote --tags`. README heads were read for scope.
Star counts and issue/security advisories could not be fetched (GitHub REST API not enabled for
unattached repos in this session). These are **TODO** before final component selection.

| Repository | License | Last commit | Latest tag | Scope | Paper / Live | Verdict |
|---|---|---|---|---|---|---|
| freqtrade/freqtrade | **GPL-3.0** | 2026-11-19 | JOSS_v3 | Crypto bot, backtest, hyperopt | Dry-run / live via CCXT | **Reference only**: copyleft would infect a proprietary platform if linked. Run isolated, if at all. |
| kernc/backtesting.py | **AGPL-3.0** | 2026-08-05 | 0.6.6 | Single-asset backtesting | Backtest only | **Do not embed** (AGPL network clause). Design reference. |
| polakowo/vectorbt | Apache-2.0 **+ Commons Clause** | 2026-11-11 | v1.2.1 | Vectorised backtests | Backtest only | **Avoid in a commercial product**: Commons Clause forbids selling. Research-only use. |
| QuantConnect/Lean | Apache-2.0 | 2026-11-20 | v2.4.0.1 | C# multi-asset engine | Paper & live | Strong but C#/.NET: an isolated service only if multi-asset institutional backtests are needed later. |
| nautechsystems/nautilus_trader | **LGPL-3.0** | 2026-11-20 | v2.0.0rc9 | Rust/Python event-driven engine | Backtest = live parity | **Best candidate for a future high-fidelity engine.** LGPL is OK as an unmodified dependency. v2 is still RC. Re-evaluate at M8+. |
| Open-Trader/opentrader | Apache-2.0 | 2025-06-29 | v1.0.0-beta.29 | TS crypto bot (grid/DCA) | Paper & live | Stale (>1 yr), beta. Reference only. |
| Jakeschincariol/day-trader-skill | MIT | 2026-10-20 | – | Claude skills; free data (Yahoo, SEC) | Paper default, human "yes" | Good **pattern reference** (human-approval gating, outcome replay). Yahoo data ToS limits commercial use. |
| Jakeschincariol/trader-skill | MIT | 2026-10-14 | – | Claude skills: 13F copy, news | Paper default | Pattern reference for News/Fundamental agents. |
| TauricResearch/TradingAgents | Apache-2.0 | 2026-11-04 | v0.7.1 | Multi-agent LLM research | Research / sim | **Adopt the design** (analyst → researcher → risk debate). Re-implemented natively behind our risk engine. |
| galleonlabs/hypergrok-trading-desk | MIT | 2026-11-17 | v1.9.0 | Hyperliquid desk, role pipeline with approval | Approval-gated | Reference for the "one send after approval" execution pattern. Hyperliquid is out of scope. |
| hummingbot/hummingbot | Apache-2.0 | 2026-11-18 | v2.18.0 | Market making, many CEX/DEX connectors | Paper & live | Heavy. Possible isolated market-making service later. Not core. |
| mementum/backtrader | **GPL-3.0** | 2023-04-19 | 1.94.15.104 | Backtesting | Live via brokers | **Unmaintained** (last commit 2023) + GPL. Reject. |
| ccxt/ccxt | **MIT** | 2026-11-20 | v4.5.93 | Unified crypto exchange API (incl. Binance) | Live (no sim) | **Selected** as the crypto exchange transport. Avoids hand-writing Binance endpoints. Pin the version and verify against Binance docs. |
| AI4Finance-Foundation/FinRL | MIT | 2026-11-18 | v0.3.8 | RL research (superseded by FinRL-X) | Research | Research only. RL is a later experiment. |
| AI4Finance-Foundation/FinRL-Trading (FinRL-X) | Apache-2.0 | 2026-09-18 | v1.0.0 | Production RL stack | Paper/live | Evaluate at M13 (self-improvement) only. |
| Polymarket/agents | MIT | 2024-11-05 | – | LLM agents for Polymarket | Live | Stale. Prediction markets are disabled pending legal review. |
| Polymarket/py-sdk | MIT | 2026-11-16 | polymarket-client-v0.20.0 | Official Polymarket SDK | Live | The adapter of choice **if** prediction markets are ever legally enabled for the owner. |
| Lumiwealth/lumibot | **GPL-3.0** | 2026-11-18 | v4.6.91 | Multi-broker bots (US focus) | Paper & live | Copyleft. Reference only for US broker adapters. |
| hummingbot/condor | MIT | 2026-11-20 | – | Telegram UI for Hummingbot API | – | Reference for owner notifications / mobile control (Tailscale advice noted). |
| Conway-Research/automaton | MIT | 2026-08-26 | v0.2.1 | "Self-replicating sovereign AI" that pays for its own compute | Autonomous | **Design reference for survival accounting only.** Its premise (no human operator, self-replication, write access to the real world) is **explicitly rejected** by our immutable policy. |

## Selection summary

* **Built natively (this repo):** indicators, strategy DSL, backtester, risk engine, paper broker,
  survival engine. This keeps licensing clean (no GPL/AGPL/Commons Clause in the core) and keeps
  the risk engine authoritative.
* **Adopt as dependencies:** `ccxt` (MIT) for crypto venues; Zerodha's official `kiteconnect` SDK
  (v5.2.2 on PyPI, MIT) for Indian equities, both pending doc verification.
* **Evaluate later in isolation:** NautilusTrader (high-fidelity engine), LEAN, Hummingbot, FinRL-X.
* **Rejected for embedding:** backtrader (unmaintained, GPL), backtesting.py (AGPL), vectorbt (Commons Clause),
  freqtrade/lumibot (GPL) — these remain reading material only.
* **Never run:** any external agent with unrestricted wallet, trading, withdrawal or replication permissions.
