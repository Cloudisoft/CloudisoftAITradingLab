# TODO

## Owner decisions / blockers
- [ ] Broker & exchange connections: **deferred by owner**. When resumed: verify official docs (developers.binance.com, kite.trade), then implement `CcxtExchange` and `KiteBroker` against `interfaces.py`.
- [ ] Approve a Railway deployment (docs/RAILWAY_DEPLOYMENT.md) so the paper loop actually runs 24×7.
- [ ] Decide operating budget and trading capital. Record real hosting costs in the ledger.
- [ ] Optional: set `ANTHROPIC_API_KEY` to enable Claude-powered agents (costed against agent budgets).
- [ ] Load exchange holiday lists (NSE/NYSE) yearly from official circulars (Settings → `/api/settings/holidays`).

## Engineering backlog
- [ ] Broker adapters + live market-data provider (blocked on the deferral above)
- [ ] Redis-backed rate limiter if ever running >1 replica (currently single replica by design)
- [ ] Persist uploaded datasets (currently in memory; re-upload after restart)
- [ ] Paper broker: resting limit orders and partial fills (backtester already models partial fills)
- [ ] Repo research: GitHub stars, open security advisories
- [ ] Email/Telegram notification channels (webhook exists)
- [ ] Docker image build check in CI (no Docker daemon in the build sandbox)
- [ ] Frontend: split `ui.tsx` helpers to silence oxlint fast-refresh warnings (cosmetic)
