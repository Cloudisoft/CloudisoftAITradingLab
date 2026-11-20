# Project Audit — Milestone 1

_Date: 2026-11-20 · Auditor: Claude Code (sole development agent)_

## 1. Where this work actually ran

The directive targets **Windows** at `C:\Projects\Cloudisoft-AI-Trading-Lab`. This session ran in a
**managed Linux cloud container** (Claude Code on the web), on a fresh clone of
`Cloudisoft/CloudisoftAITradingLab`, branch `claude/upbeat-newton-pi4w8q`. **I couldn't inspect your
Windows machine.** Run the checks in §4 there.

## 2. Existing project state

| Item | Finding |
|---|---|
| Repository | Empty: no commits, no files. Nothing to preserve or overwrite. |
| Existing code | None |
| Existing secrets | None |

## 3. Toolchain found in the build container

| Tool | Version | Status |
|---|---|---|
| git | 2.43.0 | OK |
| Python | 3.12.3 (also 3.13.18) | OK — backend pinned to 3.12 |
| uv | 0.11.32 | OK |
| Node.js | 22.23.5 | OK |
| npm | 10.9.9 | OK |
| Docker | 29.10.0 | CLI present |
| PostgreSQL client/server | 16.15 | present |
| Redis | 7.0.15 | present |
| Claude Code | 2.1.329 | OK |

## 4. Windows workstation checklist (run in PowerShell)

```powershell
git --version; python --version; uv --version; node --version; npm --version; docker --version; claude --version
```

Install only what is missing:

```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.12 -e
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Docker.DockerDesktop -e   # requires WSL2
```

Then:

```powershell
git clone https://github.com/Cloudisoft/CloudisoftAITradingLab C:\Projects\Cloudisoft-AI-Trading-Lab
cd C:\Projects\Cloudisoft-AI-Trading-Lab\backend; uv sync; uv run pytest
cd ..\frontend; npm ci; npm run build
```

## 5. Network reachability from the build container

| Host | Result | Impact |
|---|---|---|
| pypi.org, registry.npmjs.org, github.com (git) | reachable | dependencies & repo research OK |
| api.binance.com, data-api.binance.vision, developers.binance.com | **blocked** | Binance docs could not be verified; no live market data here |
| kite.trade, zerodha.com | **blocked** | Zerodha Kite Connect docs could not be verified |
| sebi.gov.in, groww.in, docs.railway.com | **blocked** | regulatory / deployment docs not verified |

Because of the directive's "never fabricate endpoints" rule, **no hand-written Binance or Zerodha
endpoint code was written.** See BROKER_INTEGRATION_MATRIX.md.

## 6. Blockers

1. Official broker docs unreachable from this environment (allow-list the hosts, or verify on the Windows machine).
2. No broker API keys (correctly — none should be shared in chat; see SECURITY.md).
3. Live trading requires owner approvals and compliance verification that only the owner can provide.
4. This container is ephemeral. It cannot run anything "24×7". The paper worker must be deployed (Railway) to run continuously.
