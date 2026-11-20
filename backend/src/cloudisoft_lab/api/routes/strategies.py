"""Strategy Lab: NL generation, versioned store, comparison, optimisation, walk-forward, improvement."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from cloudisoft_lab.agents.improvement import research_improvement
from cloudisoft_lab.agents.strategy_researcher import generate
from cloudisoft_lab.api.deps import LabDep, Operator, Owner, persist
from cloudisoft_lab.backtest.engine import CostModel, run_backtest
from cloudisoft_lab.backtest.validation import monte_carlo, out_of_sample_split
from cloudisoft_lab.data.synthetic import REGIMES, make_ohlcv
from cloudisoft_lab.governance.proposals import Proposal, ProposalKind
from cloudisoft_lab.strategy.schema import StrategyDefinition
from cloudisoft_lab.strategy.store import StrategyStoreError, compare

router = APIRouter(prefix="/api/strategies")


def _summary(r) -> dict[str, object]:  # type: ignore[no-untyped-def]
    return {"id": r.id, "name": r.name, "status": r.status, "version": r.latest.version,
            "fingerprint": r.latest.fingerprint, "versions": [
                {"version": v.version, "author": v.author, "note": v.change_note, "created_at": v.created_at,
                 "fingerprint": v.fingerprint, "backtests": v.backtests[-5:]} for v in r.versions],
            "definition": r.latest.definition.model_dump(mode="json")}


@router.get("")
async def list_strategies(lab: LabDep) -> dict[str, object]:
    return {"strategies": [_summary(r) for r in lab.strategies.items.values()]}


class DataSpec(BaseModel):
    regime: str = Field(default="volatile", pattern="|".join(REGIMES))
    bars: int = Field(default=3000, ge=300, le=20000)
    seed: int = 1
    dataset: str | None = Field(default=None, description="symbol of an uploaded dataset")
    capital: float = Field(default=1000, gt=0)
    fee_rate: float = Field(default=0.001, ge=0, le=0.05)
    min_notional: float = Field(default=5.0, ge=0)


def _data(lab: LabDep, spec: DataSpec):  # type: ignore[no-untyped-def]
    if spec.dataset:
        if spec.dataset not in lab.datasets.datasets:
            raise HTTPException(404, "dataset not uploaded")
        df, origin, src = lab.datasets.datasets[spec.dataset]
        return df, f"dataset:{spec.dataset} ({origin}, {src})"
    return make_ohlcv(spec.bars, spec.regime, seed=spec.seed), f"synthetic:{spec.regime}:seed={spec.seed}"


def _bt(lab: LabDep, s: StrategyDefinition, spec: DataSpec) -> dict[str, object]:
    df, label = _data(lab, spec)
    costs = CostModel(fee_rate=spec.fee_rate, min_notional=spec.min_notional)
    ins_df, oos_df = out_of_sample_split(df)
    full = run_backtest(df, s, spec.capital, costs)
    oos = run_backtest(oos_df, s, spec.capital, costs)
    mc = monte_carlo([t.return_pct for t in full.trades])
    return {"dataset": label, "label": full.label, "metrics": full.metrics.as_dict(),
            "out_of_sample": oos.metrics.as_dict(), "monte_carlo": mc.__dict__,
            "skipped_uneconomical": full.skipped_uneconomical}


class GenerateBody(BaseModel):
    text: str = Field(min_length=5, max_length=4000)
    data: DataSpec = Field(default_factory=DataSpec)


@router.post("/generate")
async def generate_ep(body: GenerateBody, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    try:
        d, meta = await generate(body.text, lab.llm, lab.survival.state)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    rec = lab.strategies.create(d, f"agent:strategy_researcher (for {user['sub']})", "generated from natural language")
    bt = _bt(lab, d, body.data)
    rec.latest.backtests.append(bt)
    lab.agents.log_task("strategy_researcher", "generate", "ok", source=meta.get("source"))
    lab.audit.record("strategy.generated", user["sub"], {"id": rec.id, "meta": meta})
    await persist(request)
    return {"strategy": _summary(rec), "meta": meta, "backtest": bt}


class CreateBody(BaseModel):
    definition: StrategyDefinition
    note: str = "created in builder"


@router.post("")
async def create_ep(body: CreateBody, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    rec = lab.strategies.create(body.definition, user["sub"], body.note)
    lab.audit.record("strategy.created", user["sub"], {"id": rec.id})
    await persist(request)
    return _summary(rec)


@router.post("/{sid}/versions")
async def new_version(sid: str, body: CreateBody, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    if sid not in lab.strategies.items:
        raise HTTPException(404, "not found")
    try:
        lab.strategies.add_version(sid, body.definition, user["sub"], body.note)
    except StrategyStoreError as exc:
        raise HTTPException(409, str(exc)) from exc
    lab.audit.record("strategy.version", user["sub"], {"id": sid})
    await persist(request)
    return _summary(lab.strategies.items[sid])


@router.post("/{sid}/rollback/{version}")
async def rollback(sid: str, version: int, lab: LabDep, user: Owner, request: Request) -> dict[str, object]:
    try:
        lab.strategies.rollback(sid, version, user["sub"])
    except (StrategyStoreError, KeyError) as exc:
        raise HTTPException(409, str(exc)) from exc
    lab.audit.record("strategy.rollback", user["sub"], {"id": sid, "to": version})
    await persist(request)
    return _summary(lab.strategies.items[sid])


@router.post("/{sid}/backtest")
async def backtest_ep(sid: str, spec: DataSpec, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    rec = lab.strategies.items.get(sid)
    if rec is None:
        raise HTTPException(404, "not found")
    bt = _bt(lab, rec.latest.definition, spec)
    rec.latest.backtests.append(bt)
    await persist(request)
    return bt


class CompareBody(BaseModel):
    ids: list[str] = Field(min_length=2, max_length=10)
    data: DataSpec = Field(default_factory=DataSpec)


@router.post("/compare")
async def compare_ep(body: CompareBody, lab: LabDep, user: Operator) -> dict[str, object]:
    res = {}
    for sid in body.ids:
        rec = lab.strategies.items.get(sid)
        if rec is None:
            raise HTTPException(404, f"{sid} not found")
        res[f"{rec.name} v{rec.latest.version}"] = _bt(lab, rec.latest.definition, body.data)["out_of_sample"]
    return {"basis": "out-of-sample metrics", "ranking": compare(res)}


@router.post("/{sid}/improve")
async def improve_ep(sid: str, spec: DataSpec, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    rec = lab.strategies.items.get(sid)
    if rec is None:
        raise HTTPException(404, "not found")
    df, label = _data(lab, spec)
    r = research_improvement(df, rec.latest.definition, CostModel(fee_rate=spec.fee_rate, min_notional=0), spec.capital)
    lab.agents.log_task("improvement_researcher", "walk_forward_search", "ok", improved=r.improved)
    out: dict[str, object] = {"improved": r.improved, "note": r.note, "baseline_oos_sharpe": r.baseline_oos_sharpe,
                              "best_oos_sharpe": r.best_oos_sharpe, "tested_variants": r.tested_variants, "dataset": label}
    if r.improved and r.candidate is not None:
        p = lab.board.submit(Proposal(
            ProposalKind.STRATEGY_IMPROVEMENT, f"Improve {rec.name}",
            {"strategy_id": sid, "definition": r.candidate.model_dump(mode="json")},
            {k: v for k, v in out.items() if k != "note"} | {"oos_trades": r.best_oos_trades},
            "agent:improvement_researcher"))
        out["proposal_id"] = p.id
        await lab.notifier.notify("proposal", f"Strategy improvement proposed for {rec.name}")
    await persist(request)
    return out


@router.post("/{sid}/promote")
async def promote_ep(sid: str, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    """Request that a research strategy runs in the paper loop (owner approves via proposals)."""
    rec = lab.strategies.items.get(sid)
    if rec is None:
        raise HTTPException(404, "not found")
    if not rec.latest.backtests:
        raise HTTPException(409, "run at least one backtest before promotion")
    p = lab.board.submit(Proposal(ProposalKind.STRATEGY_PROMOTION, f"Paper-trade {rec.name} v{rec.latest.version}",
                                  {"strategy_id": sid}, {"last_backtest": rec.latest.backtests[-1]}, user["sub"]))
    await persist(request)
    return {"proposal_id": p.id}


@router.post("/{sid}/pause")
async def pause_ep(sid: str, lab: LabDep, user: Operator, request: Request) -> dict[str, object]:
    if sid not in lab.strategies.items:
        raise HTTPException(404, "not found")
    lab.strategies.set_status(sid, "paused")  # pausing reduces risk: no approval needed
    lab.audit.record("strategy.paused", user["sub"], {"id": sid})
    await persist(request)
    return _summary(lab.strategies.items[sid])
