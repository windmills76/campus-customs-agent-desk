"""Route tests for the backend. They use a temporary copy of the database and stub the agent run,
so no model calls are made. Approval, cash, and reset are checked against the database values."""

import shutil

import pytest
from fastapi.testclient import TestClient

from backend.agents.team import AgentTeam
from mcp_server import shop

ORIGINAL = shop.ORIGINAL_DB


@pytest.fixture()
def client(tmp_path, monkeypatch):
    copy = tmp_path / "routes_test.db"
    shutil.copyfile(ORIGINAL, copy)
    monkeypatch.setenv("CAMPUS_DB_PATH", str(copy))
    calls = []

    async def fake_run(self, ticket_id):
        calls.append(ticket_id)

    monkeypatch.setattr(AgentTeam, "run_ticket", fake_run)
    from backend.main import app

    with TestClient(app) as test_client:
        test_client.calls = calls
        yield test_client


def test_tickets_are_open_or_resolved(client):
    tickets = client.get("/api/tickets").json()
    assert [t["id"] for t in tickets] == [101, 102, 103]
    assert {t["state"] for t in tickets} == {"open"}
    assert client.get("/api/tickets/101").json()["invoice"]["amount"] == 840.0


def test_cash_balance_comes_from_cash_accounts(client):
    body = client.get("/api/cash/balance").json()
    assert body["account"] == "checking" and body["balance"] == 3400.0


def test_run_route_starts_team_and_refuses_resolved(client):
    response = client.post("/api/tickets/102/run")
    assert response.status_code == 202
    assert client.post("/api/tickets/999/run").status_code == 400


def test_approve_pays_and_changes_cash(client):
    req = shop.request_rent_payment(1, ticket_id=102)
    response = client.post(f"/api/approvals/{req['approval_id']}/approve")
    assert response.status_code == 200 and response.json()["status"] == "approved"
    assert client.get("/api/cash/balance").json()["balance"] == 1000.0
    assert client.get("/api/approvals?status=approved").json()[0]["kind"] == "rent_payment"


def test_approve_refuses_when_cash_would_go_negative(client):
    req = shop.request_invoice_payment(501, ticket_id=101)
    with shop.connect() as c:
        c.execute("UPDATE cash_accounts SET balance = 100")
    response = client.post(f"/api/approvals/{req['approval_id']}/approve")
    assert response.status_code == 409 and "Insufficient cash" in response.json()["detail"]
    assert client.get("/api/cash/balance").json()["balance"] == 100.0
    ticket = client.get("/api/tickets").json()[0]
    assert ticket["id"] == 101 and ticket["state"] == "blocked"


def test_events_return_agent_activity(client):
    shop.add_ticket_note(101, "checked stock", agent="inventory")
    events = client.get("/api/events?ticket_id=101").json()
    assert events and events[-1]["agent"] == "inventory" and events[-1]["ticket_id"] == 101


def test_reset_restores_original_values(client):
    req = shop.request_rent_payment(1, ticket_id=102)
    client.post(f"/api/approvals/{req['approval_id']}/approve")
    response = client.post("/api/reset")
    assert response.status_code == 200 and response.json()["ok"] is True
    assert client.get("/api/cash/balance").json()["balance"] == 3400.0
    assert client.get("/api/approvals").json() == []


def test_human_answers_a_question_and_ticket_reopens(client):
    asked = shop.request_human_answer(103, "What unit price should the discount for 20 hoodies use?")
    with shop.connect() as c:
        c.execute("UPDATE tickets SET status = 'awaiting_approval' WHERE id = 103")
    response = client.post(f"/api/approvals/{asked['approval_id']}/answer", json={"answer": "Use $40.00 per unit."})
    assert response.status_code == 200
    assert client.get("/api/tickets/103").json()["status"] == "open"


def test_human_note_reaches_the_ticket(client):
    response = client.post("/api/tickets/103/notes", json={"note": "Target unit price is $29.33 per hoodie."})
    assert response.status_code == 200
    notes = client.get("/api/tickets/103").json()["notes"]
    assert "human: Target unit price is $29.33 per hoodie." in notes
    assert client.post("/api/tickets/103/notes", json={"note": "x"}).status_code == 400



def test_human_decision_starts_a_run_on_its_ticket(client):
    import time

    req = shop.request_rent_payment(1, ticket_id=102)
    response = client.post(f"/api/approvals/{req['approval_id']}/approve")
    assert response.json()["rerun_ticket_id"] == 102
    for _ in range(100):
        if client.calls:
            break
        time.sleep(0.05)
    assert client.calls == [102]
