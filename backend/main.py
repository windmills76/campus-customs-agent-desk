"""FastAPI backend for the Campus Customs agent team and its dashboard.

Start from the backend folder, so the dashboard can call http://localhost:8000:

    uvicorn main:app --reload --port 8000

Agent routes start runs and read their events. Only the human routes below change cash:
approve, reject, desk date, and reset. Agents never have access to these routes or to the
functions behind them.
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Literal

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # lets `uvicorn main:app` run from backend/ and still import mcp_server and backend.*
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from backend.agents.team import AgentTeam  # noqa: E402
from backend.models import (  # noqa: E402
    ActivityEvent,
    ApprovalDecision,
    CashBalance,
    ResetResult,
    TicketSummary,
)
from mcp_server import shop  # noqa: E402


class RejectBody(BaseModel):
    reason: str = ""


class DeskDateBody(BaseModel):
    date: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    shop.recover_interrupted_runs()  # a run cut off by a restart must not leave its ticket stuck in progress
    team = AgentTeam()
    await team.start()
    app.state.team = team
    try:
        yield
    finally:
        await team.stop()


app = FastAPI(title="Campus Customs agent team", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server for the dashboard
    allow_methods=["*"],
    allow_headers=["*"],
)


def _team() -> AgentTeam:
    return app.state.team


def _guard_idle() -> None:
    if _team().busy:
        raise HTTPException(status_code=409, detail="The agent team is running. Wait for the current run to finish.")


def _shop_call(fn: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return fn(*args, **kwargs)
    except shop.ShopError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _summary(ticket: dict[str, Any]) -> TicketSummary:
    return TicketSummary(
        id=ticket["id"],
        type=ticket["type"],
        requester=ticket["requester"],
        subject=ticket["subject"],
        status=ticket["status"],
        state=(
            "resolved" if ticket["status"] == "resolved"
            else "blocked" if ticket["status"] == "blocked"
            else "waiting" if ticket["status"] == "waiting_stock"
            else "open"
        ),
        overdue=ticket["overdue"],
        pending_approvals=ticket["pending_approvals"],
    )


# --- Health and board -------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, Any]:
    team = _team()
    return {
        "ok": True,
        "working_db": shop.working_db_path().name,
        "model": team.model_name,
        "busy": team.busy,
        "current_ticket": team.current_ticket,
        "queue": list(team.queue),
    }


@app.get("/api/tickets", response_model=list[TicketSummary])
def list_tickets() -> list[TicketSummary]:
    """Every ticket on the board, each marked open or resolved."""
    return [_summary(t) for t in shop.list_tickets()]


@app.get("/api/tickets/{ticket_id}")
def ticket_detail(ticket_id: int) -> dict[str, Any]:
    """One ticket in full: linked lease or invoice, stock, drafts, approvals, purchase orders, and notes."""
    return _shop_call(shop.get_ticket, ticket_id)


# --- Agent runs and events --------------------------------------------------


class NoteBody(BaseModel):
    note: str


class CustomerConfirmBody(BaseModel):
    accepted_qty: int


@app.post("/api/tickets/{ticket_id}/customer-confirmation")
async def customer_confirmation(ticket_id: int, body: CustomerConfirmBody) -> dict[str, Any]:
    """A person records how many units the customer accepts. The team then orders what is missing for that quantity."""
    result = _shop_call(shop.record_customer_confirmation, ticket_id, body.accepted_qty)
    _team().request_run(ticket_id, f"customer confirmed {body.accepted_qty} unit(s)")
    return result


@app.get("/api/outbox")
def outbox() -> list[dict[str, Any]]:
    """Pending customer drafts. Nothing in this outbox is ever sent by the app."""
    return shop.list_pending_drafts()


@app.post("/api/outbox/{draft_id}/ready")
def outbox_ready(draft_id: int) -> dict[str, Any]:
    """A person marks a draft ready to send. The app does not send it; the person sends it."""
    return _shop_call(shop.decide_draft, draft_id, "ready", decided_by="human")


@app.post("/api/outbox/{draft_id}/discard")
def outbox_discard(draft_id: int) -> dict[str, Any]:
    return _shop_call(shop.decide_draft, draft_id, "discarded", decided_by="human")


@app.post("/api/tickets/{ticket_id}/notes")
def add_note(ticket_id: int, body: NoteBody) -> dict[str, Any]:
    """A human adds information to a ticket, such as the target price for a discount. The next run reads it."""
    return _shop_call(shop.add_human_note, ticket_id, body.note)


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int) -> dict[str, Any]:
    """Start the agent team on one ticket. Returns at once; poll /api/events and /api/tickets for progress."""
    _guard_idle()
    ticket = _shop_call(shop.get_ticket, ticket_id)
    if ticket["status"] == "resolved":
        raise HTTPException(status_code=400, detail=f"Ticket {ticket_id} is already resolved")
    _team().launch([ticket_id], "a person started it from the dashboard")
    return {"ticket_id": ticket_id, "started": True}


@app.get("/api/events", response_model=list[ActivityEvent])
def events(
    ticket_id: int | None = None,
    after: int = Query(0, description="Return only events with an id greater than this"),
    limit: int = Query(200, le=500),
) -> list[ActivityEvent]:
    """Recent agent events, oldest first: what each agent said (message), which tools it used (tool_call, tool_result), delegations, and decisions."""
    return [ActivityEvent(**row) for row in shop.list_activity(ticket_id=ticket_id, after=after, limit=limit)]


# --- Human approvals (these change cash) ------------------------------------


def _rerun_after_decision(approval_id: int, decision: str) -> int | None:
    """A human decision on a ticket starts the team on that ticket, so it acts on the decision right away."""
    approval = next((a for a in shop.list_approvals() if a["id"] == approval_id), None)
    if approval is None or approval["ticket_id"] is None:
        return None
    if shop.get_ticket(approval["ticket_id"])["status"] == "resolved":
        return None
    _team().request_run(approval["ticket_id"], f"{decision} approval #{approval_id}")
    return approval["ticket_id"]


@app.get("/api/approvals")
def approvals(status: Literal["pending", "approved", "rejected"] | None = None) -> list[dict[str, Any]]:
    return shop.list_approvals(status=status)


@app.post("/api/approvals/{approval_id}/approve", response_model=ApprovalDecision)
async def approve(approval_id: int) -> ApprovalDecision:
    """A human clicks approve. The payment or purchase executes now, and this is the only route that changes cash.
    Refuses (409) if cash cannot cover a payment; the request stays pending with the reason."""
    result = shop.approve_approval(approval_id, decided_by="human")
    if not result["ok"]:
        raise HTTPException(status_code=409, detail=result["error"])
    rerun = _rerun_after_decision(approval_id, "approved")
    return ApprovalDecision(approval_id=approval_id, status="approved", result=result["result"], rerun_ticket_id=rerun)


class AnswerBody(BaseModel):
    answer: str


@app.post("/api/approvals/{approval_id}/answer", response_model=ApprovalDecision)
async def answer(approval_id: int, body: AnswerBody) -> ApprovalDecision:
    """A human answers a question Boss asked with ask_human. The ticket runs again with the answer."""
    result = _shop_call(shop.answer_question, approval_id, body.answer, decided_by="human")
    rerun = _rerun_after_decision(approval_id, "answered")
    return ApprovalDecision(approval_id=approval_id, status="approved", result=result["result"], rerun_ticket_id=rerun)


@app.post("/api/approvals/{approval_id}/reject", response_model=ApprovalDecision)
async def reject(approval_id: int, body: RejectBody) -> ApprovalDecision:
    _shop_call(shop.reject_approval, approval_id, reason=body.reason, decided_by="human")
    rerun = _rerun_after_decision(approval_id, "declined")
    return ApprovalDecision(approval_id=approval_id, status="rejected", result=body.reason or "rejected", rerun_ticket_id=rerun)


# --- Cash and desk ----------------------------------------------------------


@app.get("/api/cash/balance", response_model=CashBalance)
def cash_balance() -> CashBalance:
    """Current balance of the checking account, read from cash_accounts."""
    cash = shop.get_cash()
    return CashBalance(
        account=cash["name"],
        balance=cash["balance"],
        date=cash["date"],
        pending_payments=cash["pending_payments"],
        available_after_pending=cash["available_after_pending"],
    )


@app.post("/api/desk/date")
def set_desk_date(body: DeskDateBody) -> dict[str, Any]:
    """Move the shop's 'today' forward. Shipments whose ETA has arrived are received."""
    _guard_idle()
    return _shop_call(shop.set_desk_date, body.date, decided_by="human")


# --- Reset ------------------------------------------------------------------


@app.post("/api/reset", response_model=ResetResult)
def reset() -> ResetResult:
    """Replace the working copy with the original database. The original file is only read, never written."""
    _guard_idle()
    return ResetResult(**_shop_call(shop.reset_working_copy))
