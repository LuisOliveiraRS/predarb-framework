from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query

from app.paper.paper_runtime import paper_account_runtime
from app.paper.paper_risk import paper_risk_guard
from app.paper.paper_session import paper_session_manager
from app.paper.paper_session_runtime import paper_session_runtime


router = APIRouter(prefix="/paper", tags=["Paper Trading"])


def _account():
    if not paper_account_runtime.enabled:
        raise HTTPException(status_code=503, detail="Conta paper desabilitada.")
    return paper_account_runtime.account


@router.get("/status")
async def paper_status():
    return paper_account_runtime.status()


@router.get("/account")
async def paper_account_snapshot(include_trades: bool = Query(default=True)):
    return _account().snapshot(include_trades=include_trades)


@router.get("/positions")
async def paper_positions(include_closed: bool = Query(default=True)):
    return _account().positions.snapshot(include_closed=include_closed)


@router.get("/trades")
async def paper_trades():
    return _account().history.dictionaries()


@router.get("/equity")
async def paper_equity(limit: int = Query(default=500, ge=1, le=2000)):
    account = _account()
    return {
        "status": "READY",
        "mode": "PAPER",
        "curve": account.equity_tracker.snapshot(limit=limit),
        "analytics": account.equity_tracker.analytics(),
        "execution_authorized": False,
        "live_execution": False,
    }


@router.get("/statistics")
async def paper_statistics_snapshot():
    account = _account()
    snapshot = account.snapshot(include_trades=False)
    return {
        "status": "READY",
        "mode": "PAPER",
        "open_positions": snapshot["open_positions"],
        "closed_positions": snapshot["closed_positions"],
        "trade_count": snapshot["trade_count"],
        "equity": snapshot["equity"],
        "realized_pnl": snapshot["realized_pnl"],
        "unrealized_pnl": snapshot["unrealized_pnl"],
        "total_pnl": snapshot["total_pnl"],
        "return_rate": snapshot["return_rate"],
        "equity_analytics": snapshot["equity_analytics"],
        "execution_authorized": False,
        "live_execution": False,
    }


@router.post("/commit")
async def paper_commit(payload: dict[str, Any] = Body(...)):
    try:
        return _account().commit_execution(
            payload.get("orders", []),
            payload.get("reports", []),
            execution_id=payload.get("execution_id"),
            persist=bool(payload.get("persist", True)),
        )
    except (TypeError, ValueError, LookupError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/mark")
async def paper_mark(payload: dict[str, Any] = Body(...)):
    try:
        return _account().mark_to_market(
            payload.get("prices", {}),
            persist=bool(payload.get("persist", False)),
        )
    except (TypeError, ValueError, LookupError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/settle/{position_id}")
async def paper_settle(position_id: str, payload: dict[str, Any] = Body(...)):
    try:
        return _account().settle(
            position_id,
            payload.get("settlement_price"),
            fee_rate=float(payload.get("fee_rate", 0.0)),
            persist=bool(payload.get("persist", True)),
        )
    except (TypeError, ValueError, LookupError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/save")
async def paper_save():
    try:
        return {
            "status": "SAVED",
            "path": _account().save(),
            "execution_authorized": False,
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/reset")
async def paper_reset(
    confirm: str = Query(...),
    persist: bool = Query(default=True),
):
    if confirm != "RESET-PAPER":
        raise HTTPException(
            status_code=400,
            detail="Confirmação inválida para reset da conta paper.",
        )
    return _account().reset(persist=persist)


@router.get("/risk/status")
async def paper_risk_status():
    return paper_risk_guard.status()


@router.get("/session/status")
async def paper_session_status():
    return paper_session_runtime.status()


@router.get("/session/report")
async def paper_session_report():
    return paper_session_manager.report()


@router.post("/session/cycle")
async def paper_session_cycle(payload: dict[str, Any] | None = Body(default=None)):
    try:
        opportunities = None if payload is None else payload.get("opportunities")
        if opportunities is None:
            return await paper_session_runtime.run_once()
        return await asyncio.to_thread(
            paper_session_manager.run_cycle,
            opportunities,
        )
    except (TypeError, ValueError, LookupError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/session/start")
async def paper_session_start(confirm: str = Query(...)):
    try:
        return await paper_session_runtime.start(confirm=confirm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/session/stop")
async def paper_session_stop():
    return await paper_session_runtime.stop()


@router.post("/session/reset-report")
async def paper_session_reset_report(confirm: str = Query(...)):
    if confirm != "RESET-PAPER-SESSION-REPORT":
        raise HTTPException(status_code=400, detail="Confirmação inválida.")
    return paper_session_manager.reset_report()
