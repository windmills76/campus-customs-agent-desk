"""Campus Customs shop rules and database access.

This module is the only code that writes to the working database.

- The MCP server (mcp_server/server.py) exposes the agent-facing subset.
- Human-only actions (approve / reject a request, move the desk date, reset the
  working copy) are imported by the FastAPI backend and are NOT exposed over MCP,
  so no agent can approve its own request.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ORIGINAL_DB = DATA_DIR / "campus_customs.db"  # reference copy: never opened for writing
DEFAULT_WORKING_DB = DATA_DIR / "campus_customs_new.db"  # the copy agents operate on
ORIGINAL_SHA256 = "23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a"

MIN_MARGIN_PCT = 0.25  # policy assumption: a sale must keep at least 25% gross margin
PAYMENT_TERMS_DAYS = 30  # vendor invoices are due 30 days after a shipment is received
CASH_ACCOUNT = "checking"  # the only account in the homework; cash only goes out

TICKET_STATUSES = ("open", "in_progress", "awaiting_approval", "waiting_stock", "resolved", "blocked")
OUTCOMES = ("resolved", "awaiting_approval", "waiting_stock", "blocked")
APPAREL_WORDS = ("hoodie", "tee", "shirt", "sweatshirt")
GOODS_WORDS = ("mug", "cap", "hat", "pin", "sticker")

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    ticket_id INTEGER,
    ref_id INTEGER,
    amount REAL NOT NULL DEFAULT 0,
    payload TEXT NOT NULL DEFAULT '{}',
    summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    requested_by TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT,
    result TEXT
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY,
    vendor_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    size TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit_cost REAL NOT NULL,
    ticket_id INTEGER,
    approval_id INTEGER,
    ordered_on TEXT NOT NULL,
    eta TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_transit',
    invoice_id INTEGER,
    received_on TEXT
);
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    agent TEXT NOT NULL,
    ticket_id INTEGER,
    event TEXT NOT NULL,
    detail TEXT NOT NULL
);
"""


class ShopError(Exception):
    """A business rule refused the action. The message is shown to agents and humans."""


# ---------------------------------------------------------------------------
# Connection and schema
# ---------------------------------------------------------------------------


def working_db_path() -> Path:
    raw = os.environ.get("CAMPUS_DB_PATH")
    path = Path(raw) if raw else DEFAULT_WORKING_DB
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if path == ORIGINAL_DB.resolve():
        raise ShopError("Refusing to write campus_customs.db: it is the untouched original. Use campus_customs_new.db.")
    return path


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Add the homework tables and ticket columns. Safe to run every time."""
    ticket_cols = {row["name"] for row in conn.execute("PRAGMA table_info(tickets)")}
    for col in ("assigned_to", "resolution", "fulfilled_at"):
        if col not in ticket_cols:
            conn.execute(f"ALTER TABLE tickets ADD COLUMN {col} TEXT")
    conn.executescript(EXTRA_SCHEMA)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(working_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        ensure_schema(conn)
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _rows(cur: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cur.fetchall()]


def _one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _today(conn: sqlite3.Connection) -> date:
    return date.fromisoformat(conn.execute("SELECT date_today FROM desk").fetchone()["date_today"])


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _add_one_month(d: date) -> date:
    year = d.year + (d.month // 12)
    month = d.month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _log(conn: sqlite3.Connection, agent: str, ticket_id: int | None, event: str, detail: str) -> None:
    conn.execute(
        "INSERT INTO activity_log (ts, agent, ticket_id, event, detail) VALUES (?, ?, ?, ?, ?)",
        (_now(), agent, ticket_id, event, detail),
    )


def _note(conn: sqlite3.Connection, ticket_id: int | None, text: str, today: date) -> None:
    if ticket_id is None:
        return
    row = conn.execute("SELECT notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        return
    line = f"[{today.isoformat()}] {text}"
    new_notes = f"{row['notes']}\n{line}" if row["notes"] else line
    conn.execute("UPDATE tickets SET notes = ? WHERE id = ?", (new_notes, ticket_id))


def _ticket_or_raise(conn: sqlite3.Connection, ticket_id: int) -> dict[str, Any]:
    ticket = _one(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    if ticket is None:
        raise ShopError(f"Ticket {ticket_id} not found")
    return ticket


def _invoice_or_raise(conn: sqlite3.Connection, invoice_id: int) -> dict[str, Any]:
    invoice = _one(conn, "SELECT * FROM invoices WHERE id = ?", (invoice_id,))
    if invoice is None:
        raise ShopError(f"Invoice {invoice_id} not found")
    return invoice


def _lease_or_raise(conn: sqlite3.Connection, lease_id: int) -> dict[str, Any]:
    lease = _one(conn, "SELECT * FROM leases WHERE id = ?", (lease_id,))
    if lease is None:
        raise ShopError(f"Lease {lease_id} not found")
    return lease


def _pricing_or_raise(conn: sqlite3.Connection, sku: str) -> dict[str, Any]:
    price = _one(conn, "SELECT * FROM pricing WHERE sku = ?", (sku,))
    if price is None:
        raise ShopError(f"No pricing row for SKU {sku}")
    return price


def _vendor_or_raise(conn: sqlite3.Connection, vendor_id: int) -> dict[str, Any]:
    vendor = _one(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
    if vendor is None:
        raise ShopError(f"Vendor {vendor_id} not found")
    return vendor


def _cash_balance(conn: sqlite3.Connection) -> float:
    row = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)).fetchone()
    if row is None:
        raise ShopError(f"No cash account named {CASH_ACCOUNT}")
    return float(row["balance"])


def _pending_payment_total(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM approvals "
        "WHERE status = 'pending' AND kind IN ('invoice_payment', 'rent_payment')"
    ).fetchone()
    return float(row["total"])


def _category(name: str) -> str:
    lowered = name.lower()
    if any(word in lowered for word in APPAREL_WORDS):
        return "apparel"
    if any(word in lowered for word in GOODS_WORDS):
        return "small goods"
    return "other"


def _vendor_matches(specialty: str, category: str) -> bool:
    specialty = specialty.lower()
    if category == "apparel":
        return "apparel" in specialty
    if category == "small goods":
        return "goods" in specialty or "mug" in specialty
    return False


def _vendor_block(conn: sqlite3.Connection, vendor_id: int) -> str | None:
    """A vendor will not ship new product while it has an open unpaid invoice."""
    invoice = conn.execute(
        "SELECT id, amount FROM invoices WHERE vendor_id = ? AND status != 'paid' ORDER BY id LIMIT 1",
        (vendor_id,),
    ).fetchone()
    if invoice:
        return f"vendor has open unpaid invoice #{invoice['id']} (${invoice['amount']:.2f}); pay it before new product ships"
    order = conn.execute(
        "SELECT id, eta FROM purchase_orders WHERE vendor_id = ? AND status = 'in_transit' ORDER BY id LIMIT 1",
        (vendor_id,),
    ).fetchone()
    if order:
        return f"purchase order #{order['id']} to this vendor is still in transit (ETA {order['eta']})"
    return None


def _create_approval(
    conn: sqlite3.Connection,
    *,
    kind: str,
    ticket_id: int | None,
    ref_id: int | None,
    amount: float,
    payload: dict[str, Any],
    summary: str,
    requested_by: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO approvals (kind, ticket_id, ref_id, amount, payload, summary, status, requested_by, requested_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
        (kind, ticket_id, ref_id, round(amount, 2), json.dumps(payload), summary, requested_by, _now()),
    )
    return int(cur.lastrowid)


def _decorate_invoice(conn: sqlite3.Connection, invoice_id: int, today: date) -> dict[str, Any] | None:
    row = _one(
        conn,
        "SELECT i.*, v.name AS vendor_name, v.lead_days FROM invoices i "
        "JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
        (invoice_id,),
    )
    if row is None:
        return None
    due = date.fromisoformat(row["due_date"])
    row["overdue"] = row["status"] != "paid" and due < today
    row["days_past_due"] = (today - due).days if row["overdue"] else 0
    return row


def _decorate_lease(conn: sqlite3.Connection, lease_id: int, today: date) -> dict[str, Any] | None:
    row = _one(conn, "SELECT * FROM leases WHERE id = ?", (lease_id,))
    if row is None:
        return None
    due = date.fromisoformat(row["next_due"])
    row["overdue"] = due < today
    row["days_until_due"] = (due - today).days
    row["cash_covers_rent"] = _cash_balance(conn) >= row["monthly_rent"]
    return row


def _decorate_ticket(conn: sqlite3.Connection, ticket: dict[str, Any], today: date) -> dict[str, Any]:
    reasons: list[str] = []
    if ticket["invoice_id"]:
        invoice = _decorate_invoice(conn, ticket["invoice_id"], today)
        if invoice and invoice["overdue"]:
            reasons.append(f"invoice #{invoice['id']} overdue {invoice['days_past_due']} days")
    if ticket["lease_id"]:
        lease = _decorate_lease(conn, ticket["lease_id"], today)
        if lease and lease["overdue"]:
            reasons.append(f"rent for {lease['space_name']} overdue since {lease['next_due']}")
    ticket["overdue"] = bool(reasons)
    ticket["overdue_reasons"] = reasons
    ticket["pending_approvals"] = conn.execute(
        "SELECT COUNT(*) AS n FROM approvals WHERE ticket_id = ? AND status = 'pending'", (ticket["id"],)
    ).fetchone()["n"]
    return ticket


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


def get_desk() -> dict[str, Any]:
    """The shop's 'today' (Desk.date_today) plus desk notes."""
    with connect() as c:
        return _one(c, "SELECT date_today, notes FROM desk") or {}


def list_tickets(status: str | None = None) -> list[dict[str, Any]]:
    """All tickets, optionally filtered by status, with overdue flags."""
    with connect() as c:
        today = _today(c)
        if status:
            rows = _rows(c.execute("SELECT * FROM tickets WHERE status = ? ORDER BY id", (status,)))
        else:
            rows = _rows(c.execute("SELECT * FROM tickets ORDER BY id"))
        return [_decorate_ticket(c, t, today) for t in rows]


def get_ticket(ticket_id: int) -> dict[str, Any]:
    """One ticket with linked lease/invoice, stock, pricing, drafts, approvals and purchase orders."""
    with connect() as c:
        today = _today(c)
        ticket = _decorate_ticket(c, _ticket_or_raise(c, ticket_id), today)
        ticket["desk_date"] = today.isoformat()
        if ticket["lease_id"]:
            ticket["lease"] = _decorate_lease(c, ticket["lease_id"], today)
        if ticket["invoice_id"]:
            ticket["invoice"] = _decorate_invoice(c, ticket["invoice_id"], today)
        if ticket["sku"]:
            ticket["pricing"] = _one(c, "SELECT * FROM pricing WHERE sku = ?", (ticket["sku"],))
            ticket["stock"] = _rows(c.execute("SELECT * FROM inventory WHERE sku = ? ORDER BY size", (ticket["sku"],)))
        if ticket["sku"] and ticket["size"]:
            on_hand = _one(c, "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (ticket["sku"], ticket["size"]))
            incoming = _rows(
                c.execute(
                    "SELECT id, qty, eta FROM purchase_orders WHERE sku = ? AND size = ? AND status = 'in_transit' ORDER BY id",
                    (ticket["sku"], ticket["size"]),
                )
            )
            ticket["on_hand"] = on_hand["qty"] if on_hand else 0
            ticket["incoming"] = incoming
            ticket["incoming_units"] = sum(p["qty"] for p in incoming)
            ticket["missing_units"] = max(0, int(ticket["qty"] or 0) - ticket["on_hand"] - ticket["incoming_units"])
        ticket["drafts"] = _rows(c.execute("SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,)))
        ticket["approvals"] = _rows(c.execute("SELECT * FROM approvals WHERE ticket_id = ? ORDER BY id", (ticket_id,)))
        ticket["purchase_orders"] = _rows(
            c.execute("SELECT * FROM purchase_orders WHERE ticket_id = ? ORDER BY id", (ticket_id,))
        )
        return ticket


def overdue_report() -> dict[str, Any]:
    """Everything past due as of the desk date: invoices, rent, and shipments past their ETA."""
    with connect() as c:
        today = _today(c)
        invoices = [
            _decorate_invoice(c, r["id"], today)
            for r in c.execute("SELECT id FROM invoices WHERE status != 'paid' ORDER BY due_date")
        ]
        leases = [_decorate_lease(c, r["id"], today) for r in c.execute("SELECT id FROM leases")]
        return {
            "desk_date": today.isoformat(),
            "overdue_invoices": [i for i in invoices if i and i["overdue"]],
            "overdue_rent": [lease for lease in leases if lease and lease["overdue"]],
            "shipments_due_now": _rows(
                c.execute("SELECT * FROM purchase_orders WHERE status = 'in_transit' AND eta <= ?", (today.isoformat(),))
            ),
        }


def check_stock(sku: str | None = None, size: str | None = None) -> list[dict[str, Any]]:
    """Inventory rows, optionally for one SKU and/or size."""
    with connect() as c:
        sql = "SELECT * FROM inventory WHERE 1=1"
        params: list[Any] = []
        if sku:
            sql += " AND sku = ?"
            params.append(sku)
        if size:
            sql += " AND size = ?"
            params.append(size)
        return _rows(c.execute(sql + " ORDER BY sku, size", params))


def restock_options(sku: str) -> dict[str, Any]:
    """Vendors that can supply this SKU, with lead time from the vendors table and whether they can ship now."""
    with connect() as c:
        today = _today(c)
        price = _pricing_or_raise(c, sku)
        item = _one(c, "SELECT name FROM inventory WHERE sku = ? LIMIT 1", (sku,))
        name = item["name"] if item else sku
        category = _category(name)
        options = []
        for vendor in _rows(c.execute("SELECT * FROM vendors ORDER BY id")):
            if not _vendor_matches(vendor["specialty"], category):
                continue
            block = _vendor_block(c, vendor["id"])
            options.append(
                {
                    "vendor_id": vendor["id"],
                    "vendor": vendor["name"],
                    "specialty": vendor["specialty"],
                    "lead_days": vendor["lead_days"],
                    "expected_arrival": (today + timedelta(days=vendor["lead_days"])).isoformat(),
                    "unit_cost": price["unit_cost"],
                    "can_order_now": block is None,
                    "blocked_reason": block,
                }
            )
        return {"sku": sku, "name": name, "category": category, "options": options}


def list_vendors() -> list[dict[str, Any]]:
    with connect() as c:
        out = []
        for vendor in _rows(c.execute("SELECT * FROM vendors ORDER BY id")):
            vendor["blocked_reason"] = _vendor_block(c, vendor["id"])
            out.append(vendor)
        return out


def get_pricing(sku: str | None = None) -> list[dict[str, Any]]:
    with connect() as c:
        if sku:
            return [_pricing_or_raise(c, sku)]
        return _rows(c.execute("SELECT * FROM pricing ORDER BY sku"))


def margin_check(sku: str, unit_price: float, qty: int = 1) -> dict[str, Any]:
    """Gross margin at a proposed unit price, against the policy floor (cost / (1 - MIN_MARGIN_PCT))."""
    with connect() as c:
        price = _pricing_or_raise(c, sku)
        cost = float(price["unit_cost"])
        floor_price = round(cost / (1 - MIN_MARGIN_PCT), 2)
        margin_pct = (float(unit_price) - cost) / float(unit_price) if unit_price else 0.0
        return {
            "sku": sku,
            "unit_cost": cost,
            "list_price": price["list_price"],
            "proposed_unit_price": float(unit_price),
            "qty": int(qty),
            "margin_pct_at_price": round(margin_pct * 100, 2),
            "margin_floor_pct": MIN_MARGIN_PCT * 100,
            "floor_unit_price": floor_price,
            "meets_floor": float(unit_price) >= floor_price,
            "total_margin": round((float(unit_price) - cost) * int(qty), 2),
        }


def get_cash() -> dict[str, Any]:
    """Cash balance, payments already waiting for approval, and what is left after those."""
    with connect() as c:
        balance = _cash_balance(c)
        pending = _pending_payment_total(c)
        account = _one(c, "SELECT * FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,))
        return {
            **(account or {}),
            "pending_payments": round(pending, 2),
            "available_after_pending": round(balance - pending, 2),
        }


def list_invoices(status: str | None = None) -> list[dict[str, Any]]:
    with connect() as c:
        today = _today(c)
        sql = "SELECT id FROM invoices"
        params: tuple = ()
        if status:
            sql += " WHERE status = ?"
            params = (status,)
        return [_decorate_invoice(c, r["id"], today) for r in c.execute(sql + " ORDER BY id", params)]


def list_payments() -> list[dict[str, Any]]:
    with connect() as c:
        return _rows(c.execute("SELECT * FROM payments ORDER BY id"))


def list_leases() -> list[dict[str, Any]]:
    with connect() as c:
        today = _today(c)
        return [_decorate_lease(c, r["id"], today) for r in c.execute("SELECT id FROM leases ORDER BY id")]


def list_approvals(status: str | None = None) -> list[dict[str, Any]]:
    with connect() as c:
        sql = (
            "SELECT a.*, t.subject AS ticket_subject FROM approvals a "
            "LEFT JOIN tickets t ON t.id = a.ticket_id"
        )
        params: tuple = ()
        if status:
            sql += " WHERE a.status = ?"
            params = (status,)
        rows = _rows(c.execute(sql + " ORDER BY a.id DESC", params))
        for row in rows:
            row["payload"] = json.loads(row["payload"] or "{}")
        return rows


def list_drafts() -> list[dict[str, Any]]:
    with connect() as c:
        return _rows(c.execute("SELECT d.*, t.subject AS ticket_subject FROM drafts d JOIN tickets t ON t.id = d.ticket_id ORDER BY d.id DESC"))


def list_purchase_orders() -> list[dict[str, Any]]:
    with connect() as c:
        return _rows(c.execute("SELECT * FROM purchase_orders ORDER BY id DESC"))


def list_activity(ticket_id: int | None = None, after: int = 0, limit: int = 200) -> list[dict[str, Any]]:
    with connect() as c:
        sql = "SELECT * FROM activity_log WHERE id > ?"
        params: list[Any] = [after]
        if ticket_id is not None:
            sql += " AND ticket_id = ?"
            params.append(ticket_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = _rows(c.execute(sql, params))
        return list(reversed(rows))


def verify_original() -> dict[str, Any]:
    """Confirm the reference database is byte-identical to the one that was delivered."""
    digest = hashlib.sha256(ORIGINAL_DB.read_bytes()).hexdigest()
    return {"path": str(ORIGINAL_DB.relative_to(ROOT)), "sha256": digest, "matches_original": digest == ORIGINAL_SHA256}


# ---------------------------------------------------------------------------
# Agent writes (every one of these is a rule-checked action)
# ---------------------------------------------------------------------------


def log_event(agent: str, ticket_id: int | None, event: str, detail: str) -> None:
    with connect() as c:
        _log(c, agent, ticket_id, event, detail)


def set_ticket_status(ticket_id: int, status: str, agent: str, assigned_to: str | None = None) -> None:
    """Used by the backend to mark a run in progress. Agents finish tickets via resolve_ticket."""
    if status not in TICKET_STATUSES:
        raise ShopError(f"Unknown ticket status {status}")
    with connect() as c:
        _ticket_or_raise(c, ticket_id)
        c.execute(
            "UPDATE tickets SET status = ?, assigned_to = COALESCE(?, assigned_to) WHERE id = ?",
            (status, assigned_to, ticket_id),
        )
        _log(c, agent, ticket_id, "status", f"status -> {status}")


def add_ticket_note(ticket_id: int, note: str, agent: str) -> dict[str, Any]:
    with connect() as c:
        today = _today(c)
        _ticket_or_raise(c, ticket_id)
        _note(c, ticket_id, f"{agent}: {note}", today)
        _log(c, agent, ticket_id, "note", note)
        return {"ok": True, "ticket_id": ticket_id}


def resolve_ticket(ticket_id: int, outcome: str, summary: str, agent: str = "boss") -> dict[str, Any]:
    """Boss's final call. outcome is resolved, awaiting_approval, waiting_stock or blocked."""
    if outcome not in OUTCOMES:
        raise ShopError(f"outcome must be one of {', '.join(OUTCOMES)}")
    with connect() as c:
        today = _today(c)
        ticket = _ticket_or_raise(c, ticket_id)
        if outcome == "resolved" and ticket["sku"] and ticket["qty"] and not ticket["fulfilled_at"]:
            on_hand = _one(c, "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (ticket["sku"], ticket["size"]))
            short = int(ticket["qty"]) - int(on_hand["qty"] if on_hand else 0)
            if short > 0:
                raise ShopError(f"cannot resolve: {short} unit(s) still short for {ticket['sku']} {ticket['size']}; use waiting_stock or blocked")
        c.execute(
            "UPDATE tickets SET status = ?, resolution = ? WHERE id = ?",
            (outcome, summary, ticket_id),
        )
        _note(c, ticket_id, f"{agent} decision -> {outcome}: {summary}", today)
        _log(c, agent, ticket_id, "decision", f"{outcome}: {summary}")
        return {"ok": True, "ticket_id": ticket_id, "status": outcome}


def fulfill_order(ticket_id: int) -> dict[str, Any]:
    """Take a customer order out of stock. Refuses if stock is short or the order is already fulfilled."""
    with connect() as c:
        today = _today(c)
        ticket = _ticket_or_raise(c, ticket_id)
        if ticket["type"] != "customer_order":
            raise ShopError(f"Ticket {ticket_id} is a {ticket['type']}, not a customer order")
        if ticket["fulfilled_at"]:
            raise ShopError(f"Ticket {ticket_id} was already fulfilled on {ticket['fulfilled_at']}")
        row = _one(c, "SELECT * FROM inventory WHERE sku = ? AND size = ?", (ticket["sku"], ticket["size"]))
        if row is None:
            raise ShopError(f"No inventory row for {ticket['sku']} size {ticket['size']}")
        qty = int(ticket["qty"] or 1)
        if row["qty"] < qty:
            raise ShopError(f"Only {row['qty']} of {ticket['sku']} {ticket['size']} on hand; need {qty}")
        c.execute("UPDATE inventory SET qty = qty - ? WHERE sku = ? AND size = ?", (qty, ticket["sku"], ticket["size"]))
        c.execute("UPDATE tickets SET fulfilled_at = ? WHERE id = ?", (today.isoformat(), ticket_id))
        _note(c, ticket_id, f"fulfilled {qty} x {ticket['sku']} {ticket['size']} from stock", today)
        _log(c, "inventory", ticket_id, "stock", f"-{qty} {ticket['sku']} {ticket['size']}")
        return {"ok": True, "ticket_id": ticket_id, "remaining_qty": row["qty"] - qty}


def list_pending_drafts() -> list[dict[str, Any]]:
    """The pending outbox: customer drafts waiting for a person to mark them ready or discard them."""
    with connect() as c:
        return _rows(
            c.execute(
                "SELECT d.*, t.subject AS ticket_subject FROM drafts d JOIN tickets t ON t.id = d.ticket_id "
                "WHERE d.status = 'draft' ORDER BY d.id"
            )
        )


def decide_draft(draft_id: int, decision: str, decided_by: str = "human") -> dict[str, Any]:
    """A person marks a draft ready to send or discards it. This never sends anything: the app has no email channel."""
    if decision not in ("ready", "discarded"):
        raise ShopError("decision must be ready or discarded")
    with connect() as c:
        today = _today(c)
        draft = _one(c, "SELECT * FROM drafts WHERE id = ?", (draft_id,))
        if draft is None:
            raise ShopError(f"Draft {draft_id} not found")
        if draft["status"] != "draft":
            raise ShopError(f"Draft {draft_id} is already {draft['status']}")
        c.execute("UPDATE drafts SET status = ? WHERE id = ?", (decision, draft_id))
        if decision == "ready":
            text = f"draft #{draft_id} marked ready to send by a person; the app did not send it"
        else:
            text = f"draft #{draft_id} discarded by a person"
        _note(c, draft["ticket_id"], text, today)
        _log(c, decided_by, draft["ticket_id"], "outbox", text)
        return {"ok": True, "draft_id": draft_id, "status": decision, "sent": False}


def create_draft(
    ticket_id: int,
    body: str,
    recipient: str,
    channel: str = "email",
    created_by: str = "customer_service",
) -> dict[str, Any]:
    """Store a customer message on the board. Nothing is sent; drafts only."""
    with connect() as c:
        today = _today(c)
        _ticket_or_raise(c, ticket_id)
        cur = c.execute(
            "INSERT INTO drafts (ticket_id, channel, recipient, body, status, created_by, created_at) "
            "VALUES (?, ?, ?, ?, 'draft', ?, ?)",
            (ticket_id, channel, recipient, body, created_by, _now()),
        )
        _note(c, ticket_id, f"draft #{cur.lastrowid} written for {recipient} (not sent)", today)
        _log(c, created_by, ticket_id, "draft", f"draft #{cur.lastrowid} for {recipient}")
        return {"ok": True, "draft_id": cur.lastrowid, "status": "draft"}


def _committed_cash(c: sqlite3.Connection) -> float:
    """Cash left after payments awaiting approval and every open vendor bill."""
    open_bills = c.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM invoices WHERE status != 'paid'").fetchone()["total"]
    return _cash_balance(c) - _pending_payment_total(c) - float(open_bills)


def request_purchase_order(
    vendor_id: int,
    sku: str,
    size: str,
    qty: int,
    ticket_id: int | None = None,
    requested_by: str = "accounting",
) -> dict[str, Any]:
    """Prepare a restock order for human approval. Refuses if the vendor is blocked right now."""
    qty = int(qty)
    if qty <= 0:
        raise ShopError("qty must be positive")
    with connect() as c:
        today = _today(c)
        vendor = _vendor_or_raise(c, vendor_id)
        price = _pricing_or_raise(c, sku)
        if _one(c, "SELECT 1 AS ok FROM inventory WHERE sku = ? AND size = ?", (sku, size)) is None:
            raise ShopError(f"No inventory row for {sku} size {size}")
        block = _vendor_block(c, vendor_id)
        if block:
            raise ShopError(f"{vendor['name']} cannot ship yet: {block}")
        amount = qty * float(price["unit_cost"])
        committed = _committed_cash(c)
        if amount > committed:
            raise ShopError(
                f"Not enough committed cash for this order: its invoice would be ${amount:.2f}, "
                f"and checking has ${committed:.2f} after pending payments and open bills"
            )
        eta = today + timedelta(days=vendor["lead_days"])
        summary = (
            f"Order {qty} x {sku} ({size}) from {vendor['name']} at ${price['unit_cost']:.2f}, "
            f"total ${amount:.2f}, ETA {eta.isoformat()}"
        )
        payload = {"vendor_id": vendor_id, "sku": sku, "size": size, "qty": qty, "unit_cost": price["unit_cost"]}
        approval_id = _create_approval(
            c,
            kind="purchase_order",
            ticket_id=ticket_id,
            ref_id=vendor_id,
            amount=amount,
            payload=payload,
            summary=summary,
            requested_by=requested_by,
        )
        _note(c, ticket_id, f"purchase order requested (approval #{approval_id}): {summary}", today)
        _log(c, requested_by, ticket_id, "approval_request", summary)
        return {"ok": True, "approval_id": approval_id, "summary": summary}


def request_invoice_payment(invoice_id: int, ticket_id: int | None = None, requested_by: str = "accounting") -> dict[str, Any]:
    """Prepare payment of a vendor invoice for human approval. Refuses if cash cannot cover it."""
    with connect() as c:
        today = _today(c)
        invoice = _invoice_or_raise(c, invoice_id)
        if invoice["status"] == "paid":
            raise ShopError(f"Invoice #{invoice_id} is already paid")
        existing = _one(
            c,
            "SELECT id FROM approvals WHERE kind = 'invoice_payment' AND ref_id = ? AND status = 'pending'",
            (invoice_id,),
        )
        if existing:
            return {"ok": True, "approval_id": existing["id"], "note": "already waiting for approval"}
        available = _cash_balance(c) - _pending_payment_total(c)
        if invoice["amount"] > available:
            raise ShopError(
                f"Not enough cash to request this payment: invoice ${invoice['amount']:.2f}, "
                f"available after pending payments ${available:.2f}"
            )
        summary = f"Pay invoice #{invoice_id} ({invoice['description'] or 'vendor invoice'}) ${invoice['amount']:.2f}"
        approval_id = _create_approval(
            c,
            kind="invoice_payment",
            ticket_id=ticket_id,
            ref_id=invoice_id,
            amount=invoice["amount"],
            payload={"invoice_id": invoice_id, "vendor_id": invoice["vendor_id"]},
            summary=summary,
            requested_by=requested_by,
        )
        _note(c, ticket_id, f"payment requested (approval #{approval_id}): {summary}", today)
        _log(c, requested_by, ticket_id, "approval_request", summary)
        return {"ok": True, "approval_id": approval_id, "summary": summary}


def request_rent_payment(lease_id: int, ticket_id: int | None = None, requested_by: str = "facilities") -> dict[str, Any]:
    """Prepare a rent payment for human approval. Refuses if cash cannot cover it."""
    with connect() as c:
        today = _today(c)
        lease = _lease_or_raise(c, lease_id)
        existing = _one(
            c,
            "SELECT id FROM approvals WHERE kind = 'rent_payment' AND ref_id = ? AND status = 'pending'",
            (lease_id,),
        )
        if existing:
            return {"ok": True, "approval_id": existing["id"], "note": "already waiting for approval"}
        available = _cash_balance(c) - _pending_payment_total(c)
        if lease["monthly_rent"] > available:
            raise ShopError(
                f"Not enough cash for rent: ${lease['monthly_rent']:.2f} due, available ${available:.2f}"
            )
        summary = f"Pay rent for {lease['space_name']} to {lease['landlord']} ${lease['monthly_rent']:.2f} (due {lease['next_due']})"
        approval_id = _create_approval(
            c,
            kind="rent_payment",
            ticket_id=ticket_id,
            ref_id=lease_id,
            amount=lease["monthly_rent"],
            payload={"lease_id": lease_id},
            summary=summary,
            requested_by=requested_by,
        )
        _note(c, ticket_id, f"rent payment requested (approval #{approval_id})", today)
        _log(c, requested_by, ticket_id, "approval_request", summary)
        return {"ok": True, "approval_id": approval_id, "summary": summary}


def request_discount_approval(
    ticket_id: int,
    sku: str,
    size: str,
    qty: int,
    unit_price: float,
    requested_by: str = "accounting",
) -> dict[str, Any]:
    """Prepare a discounted price for human approval. Refuses prices below the margin floor."""
    with connect() as c:
        today = _today(c)
        _ticket_or_raise(c, ticket_id)
        price = _pricing_or_raise(c, sku)
        cost = float(price["unit_cost"])
        floor_price = round(cost / (1 - MIN_MARGIN_PCT), 2)
        if float(unit_price) < floor_price:
            raise ShopError(f"${unit_price:.2f} is below the margin floor ${floor_price:.2f} for {sku}")
        summary = (
            f"Discount {qty} x {sku} ({size}) to ${float(unit_price):.2f} each "
            f"(list ${price['list_price']:.2f}, margin {((float(unit_price) - cost) / float(unit_price)) * 100:.2f}%)"
        )
        approval_id = _create_approval(
            c,
            kind="discount",
            ticket_id=ticket_id,
            ref_id=None,
            amount=0,
            payload={"sku": sku, "size": size, "qty": int(qty), "unit_price": float(unit_price)},
            summary=summary,
            requested_by=requested_by,
        )
        _note(c, ticket_id, f"discount requested (approval #{approval_id}): {summary}", today)
        _log(c, requested_by, ticket_id, "approval_request", summary)
        return {"ok": True, "approval_id": approval_id, "summary": summary}


# ---------------------------------------------------------------------------
# Human-only actions: never exposed over MCP
# ---------------------------------------------------------------------------


def _pay_invoice(c: sqlite3.Connection, invoice_id: int, decided_by: str, today: date) -> str:
    """Pay tool. Refuses if the invoice is not open or the payment would make cash negative."""
    invoice = _invoice_or_raise(c, invoice_id)
    if invoice["status"] == "paid":
        raise ShopError(f"Invoice #{invoice_id} is already paid")
    amount = float(invoice["amount"])
    balance = _cash_balance(c)
    if balance - amount < 0:
        raise ShopError(f"Insufficient cash: balance ${balance:.2f} cannot cover ${amount:.2f}. Payment refused.")
    c.execute(
        "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES ('invoice', ?, ?, ?, ?, ?)",
        (invoice_id, amount, CASH_ACCOUNT, today.isoformat(), decided_by),
    )
    c.execute(
        "UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
        (amount, today.isoformat(), CASH_ACCOUNT),
    )
    c.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (invoice_id,))
    return f"paid invoice #{invoice_id} ${amount:.2f}; cash now ${balance - amount:.2f}"


def _pay_rent(c: sqlite3.Connection, lease_id: int, decided_by: str, today: date) -> str:
    lease = _lease_or_raise(c, lease_id)
    amount = float(lease["monthly_rent"])
    balance = _cash_balance(c)
    if balance - amount < 0:
        raise ShopError(f"Insufficient cash: balance ${balance:.2f} cannot cover rent ${amount:.2f}. Payment refused.")
    next_due = _add_one_month(date.fromisoformat(lease["next_due"]))
    c.execute(
        "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES ('rent', ?, ?, ?, ?, ?)",
        (lease_id, amount, CASH_ACCOUNT, today.isoformat(), decided_by),
    )
    c.execute(
        "UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
        (amount, today.isoformat(), CASH_ACCOUNT),
    )
    c.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due.isoformat(), lease_id))
    return f"paid rent ${amount:.2f} for {lease['space_name']}; next due {next_due.isoformat()}"


def _place_purchase_order(
    c: sqlite3.Connection, payload: dict[str, Any], approval_id: int, ticket_id: int | None, today: date
) -> str:
    vendor = _vendor_or_raise(c, payload["vendor_id"])
    block = _vendor_block(c, vendor["id"])
    if block:
        raise ShopError(f"{vendor['name']} cannot ship yet: {block}")
    amount = payload["qty"] * float(payload["unit_cost"])
    if amount > _committed_cash(c):
        raise ShopError(f"Not enough committed cash to place this order (${amount:.2f}). Payment refused.")
    eta = today + timedelta(days=vendor["lead_days"])
    cur = c.execute(
        "INSERT INTO purchase_orders (vendor_id, sku, size, qty, unit_cost, ticket_id, approval_id, ordered_on, eta, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_transit')",
        (
            vendor["id"],
            payload["sku"],
            payload["size"],
            payload["qty"],
            payload["unit_cost"],
            ticket_id,
            approval_id,
            today.isoformat(),
            eta.isoformat(),
        ),
    )
    return f"placed PO #{cur.lastrowid} with {vendor['name']}; ETA {eta.isoformat()}"


def receive_due_shipments(c: sqlite3.Connection, today: date) -> list[str]:
    """Receive every in-transit PO whose ETA has arrived: add stock and bill the vendor."""
    received: list[str] = []
    orders = _rows(
        c.execute("SELECT * FROM purchase_orders WHERE status = 'in_transit' AND eta <= ? ORDER BY id", (today.isoformat(),))
    )
    for po in orders:
        amount = round(po["qty"] * po["unit_cost"], 2)
        cur = c.execute(
            "INSERT INTO invoices (vendor_id, amount, due_date, status, description) VALUES (?, ?, ?, 'open', ?)",
            (
                po["vendor_id"],
                amount,
                (today + timedelta(days=PAYMENT_TERMS_DAYS)).isoformat(),
                f"PO #{po['id']}: {po['qty']} x {po['sku']} ({po['size']})",
            ),
        )
        c.execute("UPDATE inventory SET qty = qty + ? WHERE sku = ? AND size = ?", (po["qty"], po["sku"], po["size"]))
        c.execute(
            "UPDATE purchase_orders SET status = 'received', invoice_id = ?, received_on = ? WHERE id = ?",
            (cur.lastrowid, today.isoformat(), po["id"]),
        )
        if po["ticket_id"]:
            ticket = _one(c, "SELECT status FROM tickets WHERE id = ?", (po["ticket_id"],))
            if ticket and ticket["status"] == "waiting_stock":
                c.execute("UPDATE tickets SET status = 'open' WHERE id = ?", (po["ticket_id"],))
            _note(c, po["ticket_id"], f"PO #{po['id']} received; stock added; invoice #{cur.lastrowid} ${amount:.2f} open", today)
        _log(c, "system", po["ticket_id"], "receipt", f"PO #{po['id']} received, invoice #{cur.lastrowid}")
        received.append(f"PO #{po['id']} received, invoice #{cur.lastrowid} for ${amount:.2f}")
    return received


def request_human_answer(ticket_id: int, question: str, requested_by: str = "boss") -> dict[str, Any]:
    """Boss asks a person a question the tools cannot answer, such as a target price. The ticket waits for the answer."""
    question = question.strip()
    if len(question) < 10:
        raise ShopError("Ask a specific question of at least 10 characters")
    with connect() as c:
        today = _today(c)
        _ticket_or_raise(c, ticket_id)
        approval_id = _create_approval(
            c,
            kind="question",
            ticket_id=ticket_id,
            ref_id=None,
            amount=0,
            payload={"question": question},
            summary=f"Question for the human: {question}",
            requested_by=requested_by,
        )
        _note(c, ticket_id, f"question for the human (approval #{approval_id}): {question}", today)
        _log(c, requested_by, ticket_id, "question", question)
        return {"ok": True, "approval_id": approval_id, "summary": question}


def answer_question(approval_id: int, answer: str, decided_by: str = "human") -> dict[str, Any]:
    """A human answers a question. The answer is written to the ticket and the ticket reopens for another run."""
    answer = answer.strip()
    if not answer:
        raise ShopError("An answer cannot be empty")
    with connect() as c:
        today = _today(c)
        approval = _one(c, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if approval is None:
            raise ShopError(f"Approval {approval_id} not found")
        if approval["kind"] != "question":
            raise ShopError(f"Approval {approval_id} is a {approval['kind']}, not a question")
        if approval["status"] != "pending":
            raise ShopError(f"Question {approval_id} is already {approval['status']}")
        c.execute(
            "UPDATE approvals SET status = 'approved', decided_by = ?, decided_at = ?, result = ? WHERE id = ?",
            (decided_by, _now(), answer, approval_id),
        )
        ticket_id = approval["ticket_id"]
        _note(c, ticket_id, f"human answered question #{approval_id}: {answer}", today)
        if ticket_id:
            c.execute("UPDATE tickets SET status = 'open' WHERE id = ? AND status = 'awaiting_approval'", (ticket_id,))
        _log(c, decided_by, ticket_id, "answer", answer)
        return {"ok": True, "approval_id": approval_id, "result": answer}


def approvals_decided_since(ticket_id: int, since: str) -> list[int]:
    """Approvals on this ticket that a person decided at or after `since` (a run's start time)."""
    with connect() as c:
        rows = c.execute(
            "SELECT id FROM approvals WHERE ticket_id = ? AND decided_at >= ? AND status != 'pending' ORDER BY id",
            (ticket_id, since),
        ).fetchall()
        return [r["id"] for r in rows]


def recover_interrupted_runs() -> list[int]:
    """At startup, a ticket still marked in_progress was left by a run that the server stopped. Reopen it.
    Nothing is run automatically: a person starts the next run from the dashboard."""
    with connect() as c:
        today = _today(c)
        rows = _rows(c.execute("SELECT id FROM tickets WHERE status = 'in_progress'"))
        for row in rows:
            c.execute("UPDATE tickets SET status = 'open' WHERE id = ?", (row["id"],))
            _note(c, row["id"], "reopened: the run was interrupted when the server stopped; start it again from the dashboard", today)
            _log(c, "system", row["id"], "run", "run interrupted by a server restart; ticket reopened, not run again")
        return [r["id"] for r in rows]


def reopen_ticket(ticket_id: int, reason: str) -> dict[str, Any]:
    """Put a ticket back to open so the team runs it again. Used when a run's decision is out of date."""
    with connect() as c:
        today = _today(c)
        _ticket_or_raise(c, ticket_id)
        c.execute("UPDATE tickets SET status = 'open' WHERE id = ?", (ticket_id,))
        _note(c, ticket_id, f"reopened: {reason}", today)
        _log(c, "system", ticket_id, "status", f"status -> open ({reason})")
        return {"ok": True, "ticket_id": ticket_id, "status": "open"}


def approve_approval(approval_id: int, decided_by: str = "human") -> dict[str, Any]:
    """Human approves a request and it executes now. A refusal leaves the request pending with the reason."""
    try:
        with connect() as c:
            today = _today(c)
            approval = _one(c, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
            if approval is None:
                raise ShopError(f"Approval {approval_id} not found")
            if approval["status"] != "pending":
                raise ShopError(f"Approval {approval_id} is already {approval['status']}")
            payload = json.loads(approval["payload"] or "{}")
            kind = approval["kind"]
            if kind == "invoice_payment":
                result = _pay_invoice(c, approval["ref_id"], decided_by, today)
            elif kind == "rent_payment":
                result = _pay_rent(c, approval["ref_id"], decided_by, today)
            elif kind == "purchase_order":
                result = _place_purchase_order(c, payload, approval_id, approval["ticket_id"], today)
            elif kind == "discount":
                result = f"discount approved: {approval['summary']}"
            elif kind == "question":
                raise ShopError(f"Approval {approval_id} is a question. Answer it instead of approving it.")
            else:
                raise ShopError(f"Unknown approval kind {kind}")
            c.execute(
                "UPDATE approvals SET status = 'approved', decided_by = ?, decided_at = ?, result = ? WHERE id = ?",
                (decided_by, _now(), result, approval_id),
            )
            ticket_id = approval["ticket_id"]
            _note(c, ticket_id, f"approval #{approval_id} approved by {decided_by}: {result}", today)
            if ticket_id:
                c.execute(
                    "UPDATE tickets SET status = 'open' WHERE id = ? AND status = 'awaiting_approval'",
                    (ticket_id,),
                )
            _log(c, decided_by, ticket_id, "approval", f"approved #{approval_id}: {result}")
            return {"ok": True, "approval_id": approval_id, "result": result}
    except ShopError as exc:
        with connect() as c:
            c.execute("UPDATE approvals SET result = ? WHERE id = ? AND status = 'pending'", (f"REFUSED: {exc}", approval_id))
            row = _one(c, "SELECT ticket_id FROM approvals WHERE id = ?", (approval_id,))
            ticket_id = row["ticket_id"] if row else None
            _log(c, decided_by, ticket_id, "approval_refused", str(exc))
            if ticket_id:
                c.execute("UPDATE tickets SET status = 'blocked' WHERE id = ?", (ticket_id,))
                _note(c, ticket_id, f"blocked: approval #{approval_id} refused: {exc}", _today(c))
        return {"ok": False, "approval_id": approval_id, "error": str(exc)}


def reject_approval(approval_id: int, reason: str = "", decided_by: str = "human") -> dict[str, Any]:
    with connect() as c:
        today = _today(c)
        approval = _one(c, "SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if approval is None:
            raise ShopError(f"Approval {approval_id} not found")
        if approval["status"] != "pending":
            raise ShopError(f"Approval {approval_id} is already {approval['status']}")
        c.execute(
            "UPDATE approvals SET status = 'rejected', decided_by = ?, decided_at = ?, result = ? WHERE id = ?",
            (decided_by, _now(), reason or "rejected", approval_id),
        )
        ticket_id = approval["ticket_id"]
        _note(c, ticket_id, f"approval #{approval_id} rejected by {decided_by}: {reason or 'no reason given'}", today)
        if ticket_id:
            c.execute("UPDATE tickets SET status = 'open' WHERE id = ? AND status = 'awaiting_approval'", (ticket_id,))
        _log(c, decided_by, ticket_id, "approval", f"rejected #{approval_id}: {reason}")
        return {"ok": True, "approval_id": approval_id, "status": "rejected"}


def record_customer_confirmation(ticket_id: int, accepted_qty: int) -> dict[str, Any]:
    """A person records that the customer accepts this quantity. The team may then order what is missing for it."""
    with connect() as c:
        today = _today(c)
        ticket = _ticket_or_raise(c, ticket_id)
        if not ticket["sku"] or not ticket["qty"]:
            raise ShopError("Only tickets for a specific item and quantity can be confirmed")
        if not 1 <= int(accepted_qty) <= int(ticket["qty"]):
            raise ShopError(f"accepted quantity must be between 1 and {ticket['qty']}")
        text = f"CUSTOMER CONFIRMED: the customer accepts {int(accepted_qty)} x {ticket['sku']} ({ticket['size']}). Order what is missing for that quantity."
        _note(c, ticket_id, f"human: {text}", today)
        _log(c, "human", ticket_id, "customer_confirmation", text)
        return {"ok": True, "ticket_id": ticket_id, "accepted_qty": int(accepted_qty)}


def add_human_note(ticket_id: int, note: str) -> dict[str, Any]:
    """A person answers or adds information on a ticket, such as a target price. Boss reads it on the next run."""
    note = note.strip()
    if len(note) < 3:
        raise ShopError("A note needs at least 3 characters")
    with connect() as c:
        today = _today(c)
        _ticket_or_raise(c, ticket_id)
        _note(c, ticket_id, f"human: {note}", today)
        _log(c, "human", ticket_id, "note", note)
        return {"ok": True, "ticket_id": ticket_id, "note": note}


def set_desk_date(new_date: str, decided_by: str = "human") -> dict[str, Any]:
    """Move the shop's 'today' forward. Shipments whose ETA has arrived are received."""
    target = date.fromisoformat(new_date)
    with connect() as c:
        current = _today(c)
        if target < current:
            raise ShopError(f"Desk date cannot move backwards ({current.isoformat()} -> {target.isoformat()})")
        c.execute("UPDATE desk SET date_today = ?", (target.isoformat(),))
        received = receive_due_shipments(c, target)
        _log(c, decided_by, None, "desk_date", f"desk date {current.isoformat()} -> {target.isoformat()}")
        return {"ok": True, "date_today": target.isoformat(), "received": received}


def reset_working_copy() -> dict[str, Any]:
    """Replace the working copy with the original data. The original itself is only read."""
    check = verify_original()
    if not check["matches_original"]:
        raise ShopError("The reference campus_customs.db no longer matches the delivered hash; refusing to reset from it")
    target = working_db_path()
    tmp = target.with_suffix(".reset.tmp")
    shutil.copyfile(ORIGINAL_DB, tmp)
    os.replace(tmp, target)
    with connect() as c:
        _log(c, "human", None, "reset", f"working copy reset from {ORIGINAL_DB.name}")
    return {"ok": True, "working_db": target.name, "reset_from": check["path"]}


def board_counts() -> dict[str, int]:
    with connect() as c:
        counts = {status: 0 for status in TICKET_STATUSES}
        for row in c.execute("SELECT status, COUNT(*) AS n FROM tickets GROUP BY status"):
            counts[row["status"]] = row["n"]
        return counts
