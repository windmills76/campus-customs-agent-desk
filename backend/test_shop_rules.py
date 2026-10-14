"""Business-rule tests for the Campus Customs shop. Each test uses a fresh copy of the database."""

import asyncio
import hashlib
from datetime import date

import pytest

from mcp_server import shop

ROOT_DB_HASH = "23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a"


def _cash(shop):
    return shop.get_cash()["balance"]


def test_original_database_is_untouched():
    assert shop.verify_original()["matches_original"]
    assert hashlib.sha256(shop.ORIGINAL_DB.read_bytes()).hexdigest() == ROOT_DB_HASH


def test_original_database_cannot_be_used_as_working_copy(monkeypatch):
    monkeypatch.setenv("CAMPUS_DB_PATH", str(shop.ORIGINAL_DB))
    with pytest.raises(shop.ShopError):
        shop.get_desk()


def test_desk_date_drives_overdue(shop_db):
    assert shop_db.get_desk()["date_today"] == "2026-08-31"
    invoice = shop_db.list_invoices(status="open")[0]
    assert invoice["id"] == 501 and invoice["overdue"] is True
    assert shop_db.list_leases()[0]["overdue"] is False  # rent due 2026-09-02, two days out


def test_pay_refuses_when_cash_would_go_negative(shop_db):
    req = shop_db.request_invoice_payment(501, ticket_id=101)
    # Drain cash below the $840 invoice after the request was made.
    with shop_db.connect() as c:
        c.execute("UPDATE cash_accounts SET balance = 100")
    result = shop_db.approve_approval(req["approval_id"], decided_by="human")
    assert result["ok"] is False and "Insufficient cash" in result["error"]
    assert shop_db.list_approvals(status="pending")[0]["id"] == req["approval_id"]
    assert shop_db.list_invoices(status="open")[0]["id"] == 501
    assert _cash(shop_db) == 100
    assert shop_db.list_payments() == []


def test_request_refused_when_cash_cannot_cover(shop_db):
    with shop_db.connect() as c:
        c.execute("UPDATE cash_accounts SET balance = 100")
    with pytest.raises(shop.ShopError, match="Not enough cash"):
        shop_db.request_invoice_payment(501)


def test_approved_invoice_payment_updates_every_table(shop_db):
    req = shop_db.request_invoice_payment(501, ticket_id=101)
    result = shop_db.approve_approval(req["approval_id"], decided_by="human")
    assert result["ok"] is True
    assert _cash(shop_db) == pytest.approx(3400 - 840)
    payments = shop_db.list_payments()
    assert len(payments) == 1
    assert payments[0]["kind"] == "invoice" and payments[0]["ref_id"] == 501
    assert payments[0]["amount"] == 840 and payments[0]["approved_by"] == "human"
    assert shop_db.get_ticket(101)["status"] == "open"  # reopened for a re-run
    assert shop_db.list_invoices()[0]["status"] == "paid"


def test_rent_payment_advances_next_due(shop_db):
    req = shop_db.request_rent_payment(1, ticket_id=102)
    shop_db.approve_approval(req["approval_id"], decided_by="human")
    lease = shop_db.list_leases()[0]
    assert lease["next_due"] == "2026-10-02"
    assert _cash(shop_db) == pytest.approx(3400 - 2400)
    assert shop_db.list_payments()[0]["kind"] == "rent"


def test_vendor_with_open_invoice_cannot_ship(shop_db):
    with pytest.raises(shop.ShopError, match="open unpaid invoice #501"):
        shop_db.request_purchase_order(1, "CC-TEE-WHITE", "S", 10, ticket_id=101)


def test_restock_flow_after_bill_is_paid(shop_db):
    pay = shop_db.request_invoice_payment(501)
    shop_db.approve_approval(pay["approval_id"], decided_by="human")

    po = shop_db.request_purchase_order(1, "CC-TEE-WHITE", "S", 10, ticket_id=101)
    shop_db.approve_approval(po["approval_id"], decided_by="human")

    orders = shop_db.list_purchase_orders()
    assert orders[0]["status"] == "in_transit"
    assert orders[0]["eta"] == "2026-09-05"  # 2026-08-31 + 5 lead days from the vendors table
    assert shop_db.check_stock("CC-TEE-WHITE", "S")[0]["qty"] == 0  # nothing received yet

    # Vendor is blocked again while the shipment is in transit.
    with pytest.raises(shop.ShopError, match="in transit"):
        shop_db.request_purchase_order(1, "CC-TEE-WHITE", "M", 2)

    summary = shop_db.set_desk_date("2026-09-05")
    assert summary["received"] and "invoice" in summary["received"][0]
    assert shop_db.check_stock("CC-TEE-WHITE", "S")[0]["qty"] == 10
    new_invoice = shop_db.list_invoices(status="open")[0]
    assert new_invoice["amount"] == pytest.approx(80.0) and new_invoice["vendor_id"] == 1
    assert shop_db.get_ticket(101)["status"] == "open"


def test_fulfill_refuses_when_short_then_fulfills(shop_db):
    with pytest.raises(shop.ShopError, match="Only 0"):
        shop_db.fulfill_order(101)
    shop_db.set_desk_date("2026-08-31")  # no-op, still allowed
    with shop_db.connect() as c:
        c.execute("UPDATE inventory SET qty = 3 WHERE sku = 'CC-TEE-WHITE' AND size = 'S'")
    result = shop_db.fulfill_order(101)
    assert result["remaining_qty"] == 2
    with pytest.raises(shop.ShopError, match="already fulfilled"):
        shop_db.fulfill_order(101)


def test_discount_below_margin_floor_is_refused(shop_db):
    with pytest.raises(shop.ShopError, match="margin floor"):
        shop_db.request_discount_approval(103, "CC-HOOD-NAVY", "M", 20, 25.0)
    ok = shop_db.request_discount_approval(103, "CC-HOOD-NAVY", "M", 20, 40.0)
    assert ok["approval_id"]


def test_desk_date_cannot_move_backwards(shop_db):
    with pytest.raises(shop.ShopError, match="backwards"):
        shop_db.set_desk_date("2026-08-01")


def test_drafts_are_stored_not_sent(shop_db):
    draft = shop_db.create_draft(101, body="Hi Tauhid, we are restocking your size S tee.", recipient="Tauhid Zaman")
    assert draft["status"] == "draft"
    assert shop_db.get_ticket(101)["drafts"][0]["body"].startswith("Hi Tauhid")


def test_reset_restores_original_values(shop_db):
    req = shop_db.request_invoice_payment(501)
    shop_db.approve_approval(req["approval_id"], decided_by="human")
    shop_db.reset_working_copy()
    assert _cash(shop_db) == 3400
    assert shop_db.list_invoices(status="open")[0]["id"] == 501
    assert shop_db.list_payments() == []


def test_boss_question_is_answered_by_human_only(shop_db):
    asked = shop_db.request_human_answer(103, "What unit price should the discount for 20 hoodies use?")
    assert asked["approval_id"]
    # A question cannot be approved as if it were a payment.
    refused = shop_db.approve_approval(asked["approval_id"])
    assert refused["ok"] is False and "Answer it" in refused["error"]
    answered = shop_db.answer_question(asked["approval_id"], "Use $40.00 per unit.")
    assert answered["ok"] is True
    ticket = shop_db.get_ticket(103)
    assert "Use $40.00 per unit." in ticket["notes"]
    assert shop_db.list_approvals(status="approved")[0]["kind"] == "question"


def test_question_is_short_or_empty_is_refused(shop_db):
    with pytest.raises(shop.ShopError):
        shop_db.request_human_answer(103, "price?")


def test_approvals_decided_during_a_run_are_found(shop_db):
    started = "2026-10-10T13:00:00"
    req = shop_db.request_rent_payment(1, ticket_id=102)
    assert shop_db.approvals_decided_since(102, started) == []
    shop_db.approve_approval(req["approval_id"], decided_by="human")
    assert shop_db.approvals_decided_since(102, started) == [req["approval_id"]]
    assert shop_db.approvals_decided_since(102, "2100-01-01T00:00:00") == []


def test_reopen_ticket_sets_open_with_a_note(shop_db):
    shop_db.reopen_ticket(101, "test reason")
    ticket = shop_db.get_ticket(101)
    assert ticket["status"] == "open" and "reopened: test reason" in ticket["notes"]

