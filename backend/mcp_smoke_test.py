"""Smoke test for the campus-customs MCP server.

Reads the server definition from .mcp.json, launches it exactly as that file says (over stdio),
calls each of the three tools with a prompt, and checks every output against a separate
read-only query on data/campus_customs_new.db. Evidence is written to output/mcp_smoke.json.

Run from the project root:  ./.venv/bin/python backend/mcp_smoke_test.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "campus_customs_new.db"
OUT = ROOT / "output" / "mcp_smoke.json"


def _db_query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = sqlite3.connect(f"{DB.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _server_params() -> StdioServerParameters:
    config = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]["campus-customs"]
    env = {**os.environ, **config.get("env", {})}
    return StdioServerParameters(command=config["command"], args=config["args"], env=env, cwd=config["cwd"])


def _check(label: str, actual: Any, expected: Any) -> dict[str, Any]:
    return {"field": label, "tool_value": actual, "database_value": expected, "match": actual == expected}


async def _call(session: ClientSession, tool: str, arguments: dict[str, Any]) -> Any:
    result = await session.call_tool(tool, arguments)
    if result.isError:
        raise RuntimeError(f"{tool} returned an error: {result.content}")
    return json.loads(result.content[0].text)


def _case_inventory(output: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row = _db_query(
        "SELECT sku, name, size, qty, location FROM inventory WHERE sku = 'CC-HOOD-NAVY' AND size = 'M'"
    )[0]
    needed = 20
    checks = [
        _check("sku", output["sku"], row["sku"]),
        _check("name", output["name"], row["name"]),
        _check("size", output["size"], row["size"]),
        _check("on_hand", output["on_hand"], row["qty"]),
        _check("shortfall", output["shortfall"], max(0, needed - row["qty"])),
        _check("location", output["location"], row["location"]),
    ]
    return row, checks


def _case_invoices(output: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    desk = _db_query("SELECT date_today FROM desk")[0]["date_today"]
    rows = _db_query(
        "SELECT i.id, i.vendor_id, v.name AS vendor_name, v.lead_days, i.amount, i.due_date "
        "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.status = 'open' ORDER BY i.due_date, i.id"
    )
    overdue_days = (datetime.fromisoformat(desk) - datetime.fromisoformat(rows[0]["due_date"])).days
    checks = [
        _check("desk_date", output["desk_date"], desk),
        _check("open_invoice_count", len(output["open_invoices"]), len(rows)),
        _check("invoice_id", output["open_invoices"][0]["invoice_id"], rows[0]["id"]),
        _check("vendor_name", output["open_invoices"][0]["vendor_name"], rows[0]["vendor_name"]),
        _check("lead_days", output["open_invoices"][0]["lead_days"], rows[0]["lead_days"]),
        _check("amount", output["open_invoices"][0]["amount"], rows[0]["amount"]),
        _check("due_date", output["open_invoices"][0]["due_date"], rows[0]["due_date"]),
        _check("days_past_due", output["open_invoices"][0]["days_past_due"], overdue_days),
        _check("vendor_ids_blocked_from_shipping", output["vendor_ids_blocked_from_shipping"], sorted({rows[0]["vendor_id"]})),
    ]
    return rows[0], checks


def _case_lease(output: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lease = _db_query("SELECT * FROM leases WHERE id = 1")[0]
    desk = _db_query("SELECT date_today FROM desk")[0]["date_today"]
    days = (datetime.fromisoformat(lease["next_due"]) - datetime.fromisoformat(desk)).days
    checks = [
        _check("space_name", output["space_name"], lease["space_name"]),
        _check("landlord", output["landlord"], lease["landlord"]),
        _check("monthly_rent", output["monthly_rent"], lease["monthly_rent"]),
        _check("next_due", output["next_due"], lease["next_due"]),
        _check("days_until_due", output["days_until_due"], days),
        _check("overdue", output["overdue"], days < 0),
    ]
    return lease, checks


async def main() -> None:
    cases = [
        {
            "tool": "check_inventory_stock",
            "prompt": "A customer wants 20 size M Basic Hoodie Big Yale (CC-HOOD-NAVY). How many do we have, and how many are short?",
            "arguments": {"sku": "CC-HOOD-NAVY", "size": "M", "qty_needed": 20},
            "check": _case_inventory,
            "ticket": 103,
        },
        {
            "tool": "list_open_vendor_invoices",
            "prompt": "Which vendor invoices are still unpaid, and is any of them past due?",
            "arguments": {},
            "check": _case_invoices,
            "ticket": 101,
        },
        {
            "tool": "get_lease_rent_status",
            "prompt": "When is the rent due on lease 1 (Chapel Street shop), and is it overdue?",
            "arguments": {"lease_id": 1},
            "check": _case_lease,
            "ticket": 102,
        },
    ]

    evidence: dict[str, Any] = {
        "server": "campus-customs",
        "connection_file": ".mcp.json",
        "transport": "stdio, launched from .mcp.json",
        "database": "data/campus_customs_new.db",
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "tools_registered": [],
        "tests": [],
    }

    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            evidence["tools_registered"] = sorted(t.name for t in (await session.list_tools()).tools)

            for case in cases:
                output = await _call(session, case["tool"], case["arguments"])
                db_row, checks = case["check"](output)
                evidence["tests"].append(
                    {
                        "ticket": case["ticket"],
                        "prompt": case["prompt"],
                        "tool": case["tool"],
                        "arguments": case["arguments"],
                        "tool_output": output,
                        "database_row": db_row,
                        "checks": checks,
                        "all_match_database": all(c["match"] for c in checks),
                    }
                )

    evidence["all_passed"] = all(t["all_match_database"] for t in evidence["tests"])
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(evidence, indent=2, default=str) + "\n")
    for t in evidence["tests"]:
        status = "MATCH" if t["all_match_database"] else "MISMATCH"
        print(f"{status:9} {t['tool']} (ticket {t['ticket']})")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    asyncio.run(main())
