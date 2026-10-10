# Campus Customs MCP server

## What it is for

This MCP server is the only way the Campus Customs agent team reaches the shop database. Boss, inventory, accounting, facilities, and customer service all call these tools rather than writing SQL. One server means every agent sees the same numbers, and the shop rules (such as "today" being the desk date, cash-only payments, and drafts-only messages) are enforced in one place.

The server is built with FastMCP from the `mcp` Python package and runs over stdio. The agent team connects to it through `.mcp.json` settings, and each agent may use only the tools its role allows (see `backend/agents/`).

## Database it uses

`data/campus_customs_new.db`, the working copy. The reference copy `data/campus_customs.db` is never opened for writing. Set `CAMPUS_DB_PATH` to point the server at a different file.

- The three lookup tools open the database read-only (`mode=ro`).
- The agent tools write only through `mcp_server/shop.py`, which holds every business rule and is the only code that changes data.

## Tools

### Lookups (read-only, Problem 3)

| Tool | Reads | Ticket it helps unlock | What it returns |
|---|---|---|---|
| `check_inventory_stock(sku, size, qty_needed)` | `inventory` | 103 | On-hand units, the shortfall against the requested quantity, and the shelf location |
| `list_open_vendor_invoices(vendor_id?)` | `invoices`, `vendors`, `desk` | 101 | Unpaid invoices with vendor name, lead days, amount, due date, and overdue status on the desk date |
| `get_lease_rent_status(lease_id)` | `leases`, `desk` | 102 | Landlord, monthly rent, next due date, and days until rent is due or how overdue it is |

### Agent tools (Problem 5)

| Tool | Kind | Reads or writes | Purpose |
|---|---|---|---|
| `get_desk()` | read | `desk` | The shop's "today" and desk notes |
| `list_tickets(status?)` | read | `tickets` | The board, with overdue flags |
| `get_ticket(ticket_id)` | read | `tickets` plus linked tables | Full picture of one ticket |
| `overdue_report()` | read | `invoices`, `leases`, `purchase_orders`, `desk` | Everything past due on the desk date |
| `list_approvals(status?)` | read | `approvals` | Requests pending, approved, or rejected |
| `list_vendors()` | read | `vendors`, `invoices`, `purchase_orders` | Vendors with lead days and any shipping block |
| `get_pricing(sku?)` | read | `pricing` | Unit cost and list price |
| `margin_check(sku, unit_price, qty?)` | read | `pricing` | Margin at a proposed price against the floor |
| `restock_options(sku)` | read | `pricing`, `inventory`, `vendors`, `invoices`, `purchase_orders` | Vendors for a SKU with expected arrival and whether they can ship now |
| `get_cash()` | read | `cash_accounts`, `approvals` | Balance, pending payments, and what is still available |
| `list_invoices(status?)` | read | `invoices`, `vendors` | Vendor invoices with overdue flags |
| `list_payments()` | read | `payments` | Payments already made |
| `list_leases()` | read | `leases` | Rent, next due date, and overdue flags |
| `add_ticket_note(ticket_id, note, agent)` | write | `tickets` | Dated note on a ticket |
| `fulfill_order(ticket_id)` | write | `inventory`, `tickets` | Takes a customer order out of stock. Refuses if short. |
| `create_draft(ticket_id, recipient, body, channel?)` | write | `drafts` | Saves a customer message as a draft. Nothing is sent. |
| `ask_human(ticket_id, question)` | write | `approvals` | Boss only. Asks a person a question no tool can answer, such as a target price. The ticket waits for the answer. |
| `request_purchase_order(vendor_id, sku, size, qty, ticket_id?)` | request | `approvals` | Asks a human to approve a restock. Refuses if the vendor is blocked. |
| `request_invoice_payment(invoice_id, ticket_id?)` | request | `approvals` | Asks a human to approve paying an open invoice. Refuses if cash cannot cover it. |
| `request_rent_payment(lease_id, ticket_id?)` | request | `approvals` | Asks a human to approve rent. Refuses if cash cannot cover it. |
| `request_discount_approval(ticket_id, sku, size, qty, unit_price)` | request | `approvals` | Asks a human to approve a discounted price. Refuses prices below the floor. |

Every tool returns JSON. A rule refusal returns `{"error": "..."}` with the reason, so the agent can read it and respond. It does not raise.

## Deliberately not exposed

These actions are human-only, so no MCP tool exists for them: approve a request, reject a request, move the desk date, reset the working copy. They live in `mcp_server/shop.py` and the FastAPI backend. Payments therefore execute only after a person approves them.

## Running it

The agent team starts the server itself. To run it by hand from the project root:

```bash
python -m mcp_server.server
```

`tests/mcp_smoke.py` launches the server exactly as `.mcp.json` describes, calls the three lookup tools, and checks each result against the database.
