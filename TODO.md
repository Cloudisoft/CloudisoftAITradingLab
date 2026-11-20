# TODO

## Blockers (owner action)
- [ ] Allow-list or manually verify: developers.binance.com, kite.trade, sebi.gov.in, docs.railway.com
- [ ] Decide Kite Connect subscription (paid) vs. starting with crypto only
- [ ] Decide operating budget & trading capital. $5 can't cover hosting (see SURVIVAL_ENGINE_SPEC.md).
- [ ] Approve a Railway deployment (project, Postgres, budget)

## Next engineering tasks (in order)
- [ ] M5: persist Lab state (orders, fills, ledger, audit, survival history) via repositories. Restore on restart.
- [ ] M5: DB-backed users, TOTP 2FA, rate limiting (slowapi or Redis), security headers
- [ ] M6: `CcxtMarketData` public-data adapter (Binance) after doc verification. Candle cache.
- [ ] M6: exchange holiday calendars (NSE/BSE, NYSE)
- [ ] M8: NL → StrategyDefinition generator (LLM via ModelRouter, output validated by the pydantic schema)
- [ ] M8: visual strategy builder UI. Strategy version persistence & comparison.
- [ ] M9: limit orders that rest in the paper book, partial fills in the paper broker
- [ ] M11: Wallet & Funds UI. Withdrawal request UI with confirmation checklist.
- [ ] M12: daily/monthly reports. Owner notifications (email/Telegram).
- [ ] Repo research: fetch stars, open security advisories, dependency trees
- [ ] Frontend: code-split recharts (bundle 650 kB). Add a login gate before owner actions.
- [ ] CI: GitHub Actions running ruff, pytest, frontend build, pip-audit/npm audit
