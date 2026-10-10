"""Shared data types for the Campus Customs agent team.

- Role and outcome names (AgentName, TicketOutcome) are the only allowed values anywhere in the team.
- AgentReply is what every agent returns, whether it was asked by Boss or by another specialist.
- BossDecision is Boss's final call on a ticket. The team applies it to the board.
- DelegationRefusal is returned instead of an exception when a delegation would loop or run too deep.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
SPECIALIST_NAMES: tuple[str, ...] = ("inventory", "accounting", "facilities", "customer_service")
TicketOutcome = Literal["resolved", "awaiting_approval", "waiting_stock", "blocked"]


class TicketView(BaseModel):
    """A ticket as it sits on the board (a subset of the tickets table)."""

    id: int
    type: Literal["customer_order", "rent_notice", "price_override"] | str
    requester: str
    subject: str
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    lease_id: int | None = None
    invoice_id: int | None = None
    status: str
    notes: str | None = None
    created_at: str


class AgentReply(BaseModel):
    """What any agent returns to whoever asked it: Boss, or another specialist."""

    agent: AgentName
    ticket_id: int
    answer: str = Field(min_length=1, max_length=1500, description="Plain-language answer or report, with the ids and numbers used.")
    actions_taken: list[str] = Field(default_factory=list, description="Each tool action performed and its result.")
    approval_ids: list[int] = Field(default_factory=list, description="Approval requests created during this work.")
    draft_ids: list[int] = Field(default_factory=list, description="Customer drafts created during this work.")
    blocked: bool = False
    blocked_reason: str | None = None


class DelegationRequest(BaseModel):
    """Arguments an agent passes when it asks another agent for help."""

    question: str = Field(min_length=10, max_length=1200, description="A specific question or task with the ticket id.")


class DelegationRefusal(BaseModel):
    """Returned in place of a reply when a delegation is refused (loop or depth limit)."""

    target: AgentName
    reason: str


class BossDecision(BaseModel):
    """Boss's final call on one ticket. The team writes this to the ticket with resolve_ticket."""

    outcome: TicketOutcome
    summary: str = Field(min_length=10, max_length=600, description="What was decided and why, in one or two sentences.")
    approval_ids: list[int] = Field(default_factory=list)
    specialists_consulted: list[AgentName] = Field(default_factory=list)


class TeamRunResult(BaseModel):
    """One finished ticket run, for the activity view."""

    ticket_id: int
    outcome: TicketOutcome | Literal["failed"]
    summary: str


class TicketSummary(BaseModel):
    """One row for the dashboard board: open or resolved, plus the facts a human scans first."""

    id: int
    type: str
    requester: str
    subject: str
    status: str
    state: Literal["open", "blocked", "resolved"]
    overdue: bool
    pending_approvals: int


class ActivityEvent(BaseModel):
    """One logged agent event: a message, a tool call, a tool result, a delegation, or a decision."""

    id: int
    ts: str
    agent: str
    ticket_id: int | None
    event: str
    detail: str


class ApprovalDecision(BaseModel):
    approval_id: int
    status: str
    result: str | None = None
    rerun_ticket_id: int | None = None


class CashBalance(BaseModel):
    account: str
    balance: float
    date: str
    pending_payments: float
    available_after_pending: float


class ResetResult(BaseModel):
    ok: bool
    working_db: str
    reset_from: str
