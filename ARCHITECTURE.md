# Architecture — Milestone 3

## Principles
1. **Risk engine is the single authority.** Agents propose; `ExecutionRouter` re-runs `RiskEngine.evaluate`
   itself on every order. Callers can't pass in a decision. There is no other path to a broker.
2. **Paper and live are physically separate.** `PaperBroker` raises on non-PAPER orders. The router refuses to use
   a paper broker as a live connector. Live needs 8 gates (`LiveGates`) plus the market's `enabled_for_live` flag.
3. **Immutable safety policy.** `risk/policy.py::IMMUTABLE` is a frozen dataclass of module constants (no leverage,
   borrowing, shorting, martingale, auto-deposit/withdrawal, self-replication, risk-increase-to-survive).
   Owner-tunable `RiskConfig` can only be **tighter** than its ceilings.
4. **Every number is labelled** `actual | simulated | estimated` (`DataOrigin`).
5. **Decimal for money**, floats only inside the vectorised backtester.
6. **Everything financial is audited** in a SHA-256 hash chain (`audit.py`). Tampering is detectable.
7. **Idempotency keys** (`client_order_id`, funding `idempotency_key`) at the router, broker and DB (unique constraints).

## Component map

```
frontend (React/Vite/Tailwind) ──HTTP──> FastAPI (api/)
                                            │
                     ┌──────────────────────┴───────────────────────┐
                     │                    Lab (worker/lab.py)        │
 MarketDataProvider ─┤ scanner agent → strategy evaluator → OrderRequest
 (synthetic | ccxt*) │                                     │
                     │                          ExecutionRouter ── RiskEngine (pure)
                     │                           │        │
                     │                    PaperBroker   BrokerConnector* (live, gated)
                     │                                     
                     │ SurvivalLedger → SurvivalEngine → StatePolicy (trading on/off, scan rate, model tier)
                     │ ProfitManager (recommend only) → WithdrawalWorkflow (owner approval state machine)
                     └── AuditTrail (hash chain) → audit_logs
 * = not yet implemented (blocked on doc verification)
```

## Backend layout (`backend/src/cloudisoft_lab`)
| Package | Responsibility |
|---|---|
| `core/` | settings (safe defaults), structured logging with secret redaction, credential vault (Fernet), argon2, JWT, Decimal helpers |
| `domain/` | enums and pydantic message schemas (`OrderRequest`, `AgentMessage`, …) |
| `markets/registry.py` | per-market sessions, currency, enablement for paper/live, compliance notes, instrument filters |
| `interfaces.py` | provider-agnostic Protocols |
| `indicators.py` | causal RSI, MACD, EMA, SMA, VWAP, Bollinger, ATR, ADX, S/R, volume z-score |
| `strategy/` | JSON strategy DSL (AND/OR, nested groups, crosses), versioning by content fingerprint, templates |
| `backtest/` | event-driven engine, metrics, grid optimisation, OOS split, walk-forward, Monte Carlo |
| `risk/` | immutable policy, owner config, risk engine |
| `execution/` | paper broker, execution router |
| `survival/` | ledger, state machine, model-tier router |
| `profit/` | withdrawal recommendation and owner-approval workflow |
| `agents/` | market scanner / technical analyst (emit `AgentMessage`, cannot trade) |
| `data/` | synthetic regimes, data-quality checks |
| `db/` | SQLAlchemy 2 models, Alembic migrations |
| `worker/` | `Lab` orchestrator and the 24×7 paper loop |
| `api/` | FastAPI app, role-based deps, routes |

## Backtest execution assumptions
Signal on bar *t* close → fill at bar *t+1* open. Spread + slippage applied adversely. Fee per side.
Fills capped at 5% of bar volume (partial fills). Stops checked intrabar; if stop and target are touched in the
same bar, the **stop** is assumed. Gaps through a stop fill at the worse open. Per-bar funding for perps.
Closed-market bars can't open trades. Orders below min-notional/step are skipped and counted.
**Not yet modelled:** exchange holidays, survivorship-bias-free equity universes (needs point-in-time
constituents), order-book depth.

## Agents
Market Scanner, Technical Analyst: implemented (rule-based, no inference cost).
Fundamental, News, Sentiment, Strategy Researcher (LLM), Portfolio Analyst, Trade Reviewer,
Profit Manager (logic done), Survival Manager (logic done): see the roadmap. All communicate via
`AgentMessage`, and none hold broker credentials.

## Decisions log
| # | Decision | Why |
|---|---|---|
| ADR-1 | Native core instead of embedding freqtrade/backtrader/vectorbt | Licensing (GPL/AGPL/Commons Clause) and risk-engine authority |
| ADR-2 | `ccxt` for crypto, official `kiteconnect` for Zerodha | Maintained, MIT. Avoids fabricating endpoints. |
| ADR-3 | Simulated P&L excluded from survival economics | Directive: never count unearned money |
| ADR-4 | DEAD state latches until explicit owner recovery | "Do not automatically spend owner funds to revive" |
| ADR-5 | Fresh install with empty ledger → NORMAL (not DEAD) | Found in E2E run: otherwise a new install locks itself |
| ADR-6 | SQLite for dev/tests, PostgreSQL in Docker/Railway | Zero-setup local tests. Same Alembic migrations. |
