# Cloudisoft AI Trading Lab

An AI-assisted quantitative research, **paper-trading** and economic-survival platform.

> **Status: PAPER TRADING ONLY.** Live trading is disabled by default and needs explicit owner approval plus 8
> verified gates (see `IMPLEMENTATION_ROADMAP.md`). Nothing here guarantees profit. Historical and simulated
> results don't predict future returns.

| Doc | What it covers |
|---|---|
| [PROJECT_AUDIT.md](PROJECT_AUDIT.md) | environment, Windows setup, blockers |
| [REPOSITORY_RESEARCH.md](REPOSITORY_RESEARCH.md) | 20 reference repos: licenses, activity, verdicts |
| [ARCHITECTURE.md](ARCHITECTURE.md) | components, execution model, decisions |
| [BROKER_INTEGRATION_MATRIX.md](BROKER_INTEGRATION_MATRIX.md) | Binance / Zerodha / Groww capabilities & what to verify |
| [SECURITY.md](SECURITY.md) | controls, API-key rules, compliance |
| [SURVIVAL_ENGINE_SPEC.md](SURVIVAL_ENGINE_SPEC.md) | accounting formulas, states, the economics of $5 |
| [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | tables |
| [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) · [TODO.md](TODO.md) · [DEVELOPMENT_LOG.md](DEVELOPMENT_LOG.md) | progress |

## Quick start (Windows PowerShell or bash)
```bash
cd backend && uv sync && uv run pytest && uv run uvicorn cloudisoft_lab.api.app:app --reload
cd frontend && npm ci && npm run dev     # http://localhost:5173
```
Or with Docker: copy `.env.example` to `.env`, fill in the secrets, then `docker compose up --build` (UI on :8080, API on :8000).
