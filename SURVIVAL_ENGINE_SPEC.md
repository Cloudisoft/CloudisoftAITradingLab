# Survival Engine Specification

Implemented in `survival/ledger.py`, `survival/engine.py`, `survival/model_router.py`; tested in
`tests/test_survival_and_profit.py`.

## Ledger entries
`owner_funding_trading`, `owner_funding_operations`, `realised_trading_pnl` (signed, gross of fees),
`trading_fee`, `execution_cost`, `ai_inference_cost`, `hosting_cost`, `data_cost`, `other_expense`,
`external_revenue` (must be ACTUAL + verified, and the API requires a payment reference), `owner_withdrawal`.

Rules: owner deposits are funding, never revenue. Unrealised P&L never enters the ledger. SIMULATED trading
entries are ignored unless `count_simulated_pnl` is set (default **off**). Negative amounts are rejected
except for P&L. Trading P&L can't be entered manually through the API (it only comes from fills).

## Formulas (exactly as directed)
```
NET TRADING PROFIT   = realised P&L − trading fees − execution costs
NET OPERATING PROFIT = net trading profit + verified external revenue − AI − hosting − data − other
ELIGIBLE EARNINGS    = max(net trading profit, 0) × earnings_to_operations_fraction + verified external revenue
SURVIVAL BALANCE     = owner operating funding + eligible earnings − operating expenses
TRADING CAPITAL      = owner trading funding + net trading profit − swept share of profit − owner withdrawals
RUNWAY (days)        = survival balance ÷ average daily expenses over the last 7 days
```
The swept share appears in exactly one bucket, so there is no double counting (asserted by a test).

## States (first match wins)
| Condition | State | Policy |
|---|---|---|
| ledger empty | NORMAL (+ "record operating budget") | normal |
| DEAD previously and no owner recovery | DEAD | stop non-essential inference & execution, keep data, wait for owner |
| balance ≤ 0 | DEAD | ″ |
| runway < 3 d | CRITICAL | no new trades. Protective sells allowed. Economy model, essential only. Notify owner. |
| runway < 14 d | LOW_COMPUTE | 4× slower scans, economy model, defer non-essential jobs |
| sustained profitability (below) | PROFITABLE | normal + expansion **proposals** |
| runway ≥ 90 d or no burn | HIGH | premium model allowed |
| otherwise | NORMAL | standard model |

**PROFITABLE requires all of:** ≥ 30 days evaluated, ≥ 50 closed trades, net operating profit > 0, ≥ 60% of weekly
periods net-positive, max drawdown ≤ 20%. All are configurable (`SurvivalConfig`), with floors of 7 days / 10 trades.

## Never
Increase risk to survive · auto-deposit · auto-revive from DEAD · delete records or credentials · count
deposits/unrealised/simulated gains as earnings.

## The economics of $5 (read this)
With $5 trading capital, even a 10%/month net return (exceptional, and not something to expect) earns
$0.50/month. Typical always-on cloud hosting plus any LLM inference costs several dollars or more per month.
**The agent can't pay for itself on $5 of capital.** The engine reports that honestly (LOW_COMPUTE →
CRITICAL → DEAD as the operating budget drains). Self-sufficiency needs either much more capital
(owner decision), verified external revenue, or near-zero running costs (the rule-based scanner uses no inference).
