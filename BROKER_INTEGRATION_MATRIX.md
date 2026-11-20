# Broker & Exchange Integration Matrix

**Status legend:** ✅ implemented & tested · 🟡 designed, not implemented · ⛔ blocked · ❌ not supported / not allowed

> No row below contains endpoint paths. The official documentation (developers.binance.com,
> kite.trade) was **unreachable** from the build environment on 2026-11-20 and nothing was filled in
> from memory. Each adapter starts only after an owner/engineer verifies the items in the
> "Verify first" column against the provider's current official documentation.

| Capability | Paper (built-in) | Binance (via `ccxt`, MIT) | Zerodha (official `kiteconnect` SDK) | Groww |
|---|---|---|---|---|
| Account connection | ✅ | ⛔ docs unverified | ⛔ docs unverified | ❌ future, optional |
| Market data | ✅ synthetic | ⛔ (public klines would replace synthetic) | ⛔ (historical data may be a separately priced add-on: verify) | ❌ |
| Balances / funds & margin | ✅ simulated | ⛔ | ⛔ | ❌ |
| Place / cancel order | ✅ (idempotent) | ⛔ | ⛔ | ❌ |
| Open orders / trade history | ✅ | ⛔ | ⛔ | ❌ |
| Positions / holdings | ✅ | ⛔ (spot = balances) | ⛔ | ❌ |
| Deposit history | ✅ simulated | 🟡 read-only, if the API key permits | ❌ believed unsupported, so link to the official funds UI (verify) | ❌ |
| Withdrawal history | ✅ simulated | 🟡 read-only | ❌ believed unsupported (verify) | ❌ |
| Initiate deposit | ❌ never (no custody) | ❌ never | ❌ never | ❌ |
| Initiate withdrawal | ✅ simulated only | ❌ withdrawal permission must stay **OFF**. Owner withdraws in the Binance UI | ❌ | ❌ |

## Verify first (per provider, from official docs)

* API availability, authentication scheme, session expiry (Kite access tokens expire daily, so re-login is needed: verify).
* **Cost** (Kite Connect is a paid subscription per app: verify current price and what the free tier excludes).
* Rate limits & weights; order-rate limits; behaviour on 429/418.
* Instrument filters: min quantity, step size, min notional, tick size (feeds `Instrument`).
* API key permission scopes; **withdrawals disabled**; IP whitelisting (expected/required for Indian brokers under the SEBI retail-algo framework: verify).
* Exchange/broker algo-order tagging or registration requirements (SEBI framework for retail algo trading: verify the current circular and Zerodha's implementation).
* Commercial/ToS restrictions on redistributing market data.

## Interface mapping

Every adapter implements the Protocols in `backend/src/cloudisoft_lab/interfaces.py`:
`MarketDataProvider`, `BrokerConnector` (= `AccountConnector` + `OrderManagementInterface` + `PortfolioInterface`),
`ExchangeConnector` (alias), `FundingInterface` (history + official funding URL only),
`WithdrawalInterface` (history + submission **only** for an owner-approved request id),
`RiskManagementInterface`.
