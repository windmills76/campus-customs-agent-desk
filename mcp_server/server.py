"""Campus Customs MCP server.

Two groups of tools:

1. Three read-only lookups that never write (Problem 3 tools, kept as-is):
   - check_inventory_stock      reads inventory                 (ticket 103)
   - list_open_vendor_invoices  reads invoices, vendors, desk   (ticket 101)
   - get_lease_rent_status      reads leases, desk              (ticket 102)

2. Agent tools (Problem 5). Reads and rule-checked writes. Every write goes through
   mcp_server/shop.py, the only code that changes the working database. Human-only
   actions (approve, reject, set desk date, reset) are deliberately NOT exposed here.

The server works on data/campus_customs_new.db. Run from the project root:
    python -m mcp_server.server
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from . import shop

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "campus_customs_new.db"

mcp = FastMCP("campus-customs")


def _db_path() -> Path:
    raw = os.environ.get("CAMPUS_DB_PATH")
    path = Path(raw) if raw else DEFAULT_DB
    return path if path.is_absolute() else ROOT / path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(f"{_db_path().resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _desk_date(conn: sqlite3.Connection) -> date:
    """The shop's 'today'. Overdue checks use this, never the system clock."""
    return date.fromisoformat(conn.execute("SELECT date_today FROM desk").fetchone()["date_today"])


@mcp.tool()
def check_inventory_stock(sku: str, size: str, qty_needed: int) -> dict[str, Any]:
    """Check how many units of one SKU and size are on hand against how many an order needs.
    Reads the inventory table. Returns on_hand, shortfall (0 if stock covers the need), and the shelf location."""
    if qty_needed <= 0:
        return {"error": "qty_needed must be a positive whole number"}
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
    if row is None:
        return {"error": f"No inventory row for SKU {sku} size {size}"}
    return {
        "sku": row["sku"],
        "name": row["name"],
        "size": row["size"],
        "on_hand": row["qty"],
        "qty_needed": qty_needed,
        "shortfall": max(0, qty_needed - row["qty"]),
        "location": row["location"],
    }


@mcp.tool()
def list_open_vendor_invoices(vendor_id: int | None = None) -> dict[str, Any]:
    """List vendor invoices that are still open (unpaid), with the vendor name, lead days, amount, due date,
    and whether each is past due on the desk date. A vendor with any open invoice will not ship new product.
    Reads the invoices, vendors, and desk tables. Pass vendor_id to narrow the list to one vendor."""
    sql = (
        "SELECT i.id, i.vendor_id, v.name AS vendor_name, v.lead_days, i.amount, i.due_date, i.description "
        "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.status = 'open'"
    )
    params: tuple = ()
    if vendor_id is not None:
        sql += " AND i.vendor_id = ?"
        params = (vendor_id,)
    sql += " ORDER BY i.due_date, i.id"
    with closing(_connect()) as conn:
        today = _desk_date(conn)
        rows = conn.execute(sql, params).fetchall()
    invoices = []
    for row in rows:
        due = date.fromisoformat(row["due_date"])
        invoices.append(
            {
                "invoice_id": row["id"],
                "vendor_id": row["vendor_id"],
                "vendor_name": row["vendor_name"],
                "lead_days": row["lead_days"],
                "amount": row["amount"],
                "due_date": row["due_date"],
                "overdue": due < today,
                "days_past_due": (today - due).days if due < today else 0,
                "description": row["description"],
            }
        )
    return {
        "desk_date": today.isoformat(),
        "open_invoices": invoices,
        "vendor_ids_blocked_from_shipping": sorted({inv["vendor_id"] for inv in invoices}),
    }


@mcp.tool()
def get_lease_rent_status(lease_id: int) -> dict[str, Any]:
    """Return one lease's landlord, monthly rent, and next due date, with days until rent is due and whether
    it is overdue, both measured against the desk date. Reads the leases and desk tables."""
    with closing(_connect()) as conn:
        today = _desk_date(conn)
        row = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
    if row is None:
        return {"error": f"No lease with id {lease_id}"}
    due = date.fromisoformat(row["next_due"])
    return {
        "lease_id": row["id"],
        "space_name": row["space_name"],
        "landlord": row["landlord"],
        "monthly_rent": row["monthly_rent"],
        "next_due": row["next_due"],
        "desk_date": today.isoformat(),
        "days_until_due": (due - today).days,
        "overdue": due < today,
        "notes": row["notes"],
    }


# --- Agent tools: reads and rule-checked writes (all through shop.py) -------


def _shop(fn: Callable[..., Any], **kwargs: Any) -> str:
    """Run a shop function and return JSON. Rule refusals come back as {"error": ...} so the agent can read them."""
    try:
        return json.dumps(fn(**kwargs), default=str)
    except shop.ShopError as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def get_desk() -> str:
    """The shop's 'today' (desk.date_today) and desk notes. All overdue and due-date checks use this date."""
    return _shop(shop.get_desk)


@mcp.tool()
def list_tickets(status: str | None = None) -> str:
    """Every ticket on the board, or only those with one status (open, in_progress, awaiting_approval, waiting_stock, resolved, blocked). Includes overdue flags."""
    return _shop(shop.list_tickets, status=status)


@mcp.tool()
def get_ticket(ticket_id: int) -> str:
    """Full picture of one ticket: its lease or invoice, stock and pricing for its SKU, drafts, approvals, and purchase orders."""
    return _shop(shop.get_ticket, ticket_id=ticket_id)


@mcp.tool()
def overdue_report() -> str:
    """Everything past due on the desk date: overdue vendor invoices, overdue rent, and shipments whose ETA has arrived."""
    return _shop(shop.overdue_report)


@mcp.tool()
def list_approvals(status: str | None = None) -> str:
    """Requests waiting for a human or already decided (status: pending, approved, rejected). Read-only for agents."""
    return _shop(shop.list_approvals, status=status)


@mcp.tool()
def list_vendors() -> str:
    """Every vendor with its specialty, lead_days, and any current shipping block (blocked_reason)."""
    return _shop(shop.list_vendors)


@mcp.tool()
def get_pricing(sku: str | None = None) -> str:
    """Unit cost and list price for one SKU, or for every SKU when sku is omitted."""
    return _shop(shop.get_pricing, sku=sku)


@mcp.tool()
def margin_check(sku: str, unit_price: float, qty: int = 1) -> str:
    """Gross margin at a proposed unit price, against the margin floor. Run this before proposing any discount."""
    return _shop(shop.margin_check, sku=sku, unit_price=unit_price, qty=qty)


@mcp.tool()
def restock_options(sku: str) -> str:
    """Vendors that can supply a SKU: lead_days, expected_arrival from the desk date, and can_order_now with blocked_reason."""
    return _shop(shop.restock_options, sku=sku)


@mcp.tool()
def get_cash() -> str:
    """Cash balance in the checking account, payments already waiting for approval, and the amount still available."""
    return _shop(shop.get_cash)


@mcp.tool()
def list_invoices(status: str | None = None) -> str:
    """Vendor invoices with vendor name and overdue flag. Use status='open' for unpaid bills."""
    return _shop(shop.list_invoices, status=status)


@mcp.tool()
def list_payments() -> str:
    """Payments already made, newest last."""
    return _shop(shop.list_payments)


@mcp.tool()
def list_leases() -> str:
    """Every lease with monthly rent, next due date, days until due, and overdue flag."""
    return _shop(shop.list_leases)


@mcp.tool()
def add_ticket_note(ticket_id: int, note: str, agent: str) -> str:
    """Add a dated note to a ticket's history. agent is your role name (boss, inventory, accounting, facilities, customer_service)."""
    return _shop(shop.add_ticket_note, ticket_id=ticket_id, note=note, agent=agent)


@mcp.tool()
def fulfill_order(ticket_id: int) -> str:
    """Take a customer_order's units out of stock. Refuses if stock is short or the order was already fulfilled. Spends no cash."""
    return _shop(shop.fulfill_order, ticket_id=ticket_id)


@mcp.tool()
def create_draft(ticket_id: int, recipient: str, body: str, channel: str = "email") -> str:
    """Save a customer message as a DRAFT on the ticket. Nothing is sent to anyone."""
    return _shop(shop.create_draft, ticket_id=ticket_id, body=body, recipient=recipient, channel=channel)


@mcp.tool()
def request_purchase_order(vendor_id: int, sku: str, size: str, qty: int, ticket_id: int | None = None) -> str:
    """Request a restock order from a vendor for HUMAN approval. Refuses if the vendor is blocked (open unpaid invoice or order in transit)."""
    return _shop(shop.request_purchase_order, vendor_id=vendor_id, sku=sku, size=size, qty=qty, ticket_id=ticket_id)


@mcp.tool()
def request_invoice_payment(invoice_id: int, ticket_id: int | None = None) -> str:
    """Request payment of an open vendor invoice for HUMAN approval. Refuses if cash cannot cover it. Nothing is paid by this call."""
    return _shop(shop.request_invoice_payment, invoice_id=invoice_id, ticket_id=ticket_id)


@mcp.tool()
def request_rent_payment(lease_id: int, ticket_id: int | None = None) -> str:
    """Request a rent payment for HUMAN approval. Refuses if cash cannot cover the rent. Nothing is paid by this call."""
    return _shop(shop.request_rent_payment, lease_id=lease_id, ticket_id=ticket_id)


@mcp.tool()
def ask_human(ticket_id: int, question: str) -> str:
    """Boss only. Ask a person a question that no tool can answer, such as the target price on a discount request.
    The question appears on the dashboard and the ticket waits for the answer. Nothing is decided by this call."""
    return _shop(shop.request_human_answer, ticket_id=ticket_id, question=question, requested_by="boss")


@mcp.tool()
def request_discount_approval(ticket_id: int, sku: str, size: str, qty: int, unit_price: float) -> str:
    """Request a discounted unit price for HUMAN approval. Refuses any price below the margin floor."""
    return _shop(
        shop.request_discount_approval,
        ticket_id=ticket_id,
        sku=sku,
        size=size,
        qty=qty,
        unit_price=unit_price,
    )


if __name__ == "__main__":
    mcp.run()
