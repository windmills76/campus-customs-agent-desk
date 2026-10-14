# Campus Customs Harness

Living design document for the Campus Customs agent team. Each problem adds to it. This section covers Problem 2: studying the database.

## Data sources

- **Reference database:** `data/campus_customs.db`. Read-only. Its SHA-256 hash is `23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a`, and it is never written to.
- **Working copy:** `data/campus_customs_new.db`. A byte-identical copy of the reference, created in Problem 2. Later problems write to this copy only, and reset restores it from the reference.
- **"Today" for the shop:** `desk.date_today`, which is **2026-08-31**. The system clock is not used, because the spec says overdue checks use the shop's date.

## Tables

Field types come from `PRAGMA table_info`. "PK" marks the primary key and "FK" marks a foreign key.

### desk

The spec lists this table as "deck". The database calls it `desk`.

| Field | Type | Notes |
|---|---|---|
| date_today | TEXT, not null | The shop's "today". Every overdue check uses it. |
| notes | TEXT | Free text for the desk. Empty today. |

**Why it matters:** this single date decides what is overdue, which invoices are late, and when rent falls due.

### tickets

| Field | Type | Notes |
|---|---|---|
| id | INTEGER, PK | Ticket number shown on the board. |
| type | TEXT, not null | `customer_order`, `rent_notice`, or `price_override`. |
| requester | TEXT, not null | Customer, landlord, or org. |
| subject | TEXT, not null | Short title. |
| sku | TEXT | Set for order and discount tickets. |
| size | TEXT | Set with sku. |
| qty | INTEGER | Units requested. |
| lease_id | INTEGER, FK → leases.id | Set for rent tickets. |
| invoice_id | INTEGER, FK → invoices.id | Set when the ticket relates to a vendor bill. |
| status | TEXT, not null | Current board state. Starts as `open`. |
| notes | TEXT | Running history of the ticket. |
| created_at | TEXT, not null | Timestamp with a timezone offset. |

**Why it matters:** this is the board Boss reads on every run.

### inventory

| Field | Type | Notes |
|---|---|---|
| sku | TEXT, PK (with size) | Product code, such as `CC-HOOD-NAVY`. |
| name | TEXT, not null | Product name. |
| size | TEXT, PK (with sku) | `S`, `M`, `L`, `XL`, or `OS` (one size). |
| qty | INTEGER, not null | Units on hand. |
| location | TEXT, not null | Aisle where the product sits. |

**Why it matters:** the inventory agent compares this quantity with what a ticket needs to find a shortfall.

### pricing

| Field | Type | Notes |
|---|---|---|
| sku | TEXT, PK | One row per product. |
| unit_cost | REAL, not null | What the shop pays per unit. |
| list_price | REAL, not null | Standard selling price. |

**Why it matters:** the accounting agent uses cost and list price to check margins before any discount is approved.

### vendors

| Field | Type | Notes |
|---|---|---|
| id | INTEGER, PK | Vendor number. |
| name | TEXT, not null | Vendor name. |
| specialty | TEXT, not null | What the vendor makes (`apparel reprint`, `mugs and small goods`, `local courier`). |
| lead_days | INTEGER, not null | Days from order to arrival. |

**Why it matters:** the inventory agent matches a SKU to vendors by specialty and uses `lead_days` to estimate when restocked units arrive.

### invoices

| Field | Type | Notes |
|---|---|---|
| id | INTEGER, PK | Invoice number. |
| vendor_id | INTEGER, not null, FK → vendors.id | Who billed the shop. |
| amount | REAL, not null | Amount owed. |
| due_date | TEXT, not null | Date payment is due. Overdue when earlier than `desk.date_today`. |
| status | TEXT, not null | `open` or `paid`. Only `open` counts as owed. |
| description | TEXT | What was billed. |

**Why it matters:** a vendor with an open invoice will not ship new product.

### leases

| Field | Type | Notes |
|---|---|---|
| id | INTEGER, PK | Lease number. |
| space_name | TEXT, not null | Which space is leased. |
| landlord | TEXT, not null | Who receives rent. |
| monthly_rent | REAL, not null | Rent due each month. |
| next_due | TEXT, not null | Next rent due date. Overdue when earlier than `desk.date_today`. |
| notes | TEXT | Free text. |

**Why it matters:** the facilities agent uses `next_due` and `monthly_rent` to decide when rent must be paid and how much.

### cash_accounts

| Field | Type | Notes |
|---|---|---|
| name | TEXT, PK | Account name. Only `checking` exists. |
| balance | REAL, not null | Cash on hand. |
| date | TEXT, not null | Date of the balance. |

**Why it matters:** every payment is checked against this balance.

### payments

| Field | Type | Notes |
|---|---|---|
| id | INTEGER, PK | Payment number. |
| kind | TEXT, not null | What was paid, such as invoice or rent. |
| ref_id | INTEGER | Id of the invoice or lease paid. |
| amount | REAL, not null | Amount paid. |
| account | TEXT, not null | Account paid from (`checking`). |
| paid_at | TEXT, not null | Date paid. |
| approved_by | TEXT, not null | Who approved it. Required because human approval is mandatory. |

**Why it matters:** this is the record of cash out.

## How the three open tickets link

```
ticket 101 customer_order  (Tauhid Zaman, CC-TEE-WHITE S x1)
  ├── inventory: CC-TEE-WHITE S = 0 on hand  → shortfall 1
  ├── pricing:   cost 8.00, list 28.00
  └── invoice 501 (Bulldog Print Co, $840.00, due 2026-08-28, open)  → OVERDUE
        └── vendors 1: lead 5 days, blocks new shipments until 501 is paid

ticket 102 rent_notice  (Elm City Properties)
  └── lease 1: Chapel Street shop, $2,400.00/month, next due 2026-09-02  → due in 2 days

ticket 103 price_override  (Yale AI Club, CC-HOOD-NAVY M x20)
  ├── inventory: CC-HOOD-NAVY M = 8 on hand  → shortfall 12
  └── pricing:   cost 22.00, list 58.00
```

What the links mean for the team:

- **Ticket 101 is blocked by a bill.** The shop has no size S tee, and the only apparel vendor (Bulldog Print Co, lead 5 days) will not ship while invoice 501 is open and overdue. Accounting must pay 501 first. That needs human approval and $840 of the $3,400 cash.
- **Ticket 102 needs rent approval.** Rent of $2,400 is due 2026-09-02. Cash covers it, so it can be paid once a human approves.
- **Ticket 103 needs a restock and a margin check.** The shop is 12 hoodies short for size M. The same apparel vendor is blocked by invoice 501, so this restock also waits on the bill. At $58 list, the discount has room below list price, but accounting must check the margin.
- **Cash and vendor blocks interact.** Paying invoice 501 ($840) and rent ($2,400) together leaves $160. Any later bill or restock must fit within what remains.

## Observations and gaps

- `payments` is empty. Nothing has been paid yet, so cash equals the starting balance.
- `invoices` has one row. Only one vendor has an open bill, and it is the one the apparel tickets depend on.
- The original schema has no table for approvals, drafts, purchase orders, or activity. The app adds them to the working copy (see Tables added by the app).
- `tickets.invoice_id` on ticket 101 points to a bill for a rush reprint. The link means the bill is related to the order. It does not mean the order is paid for.
- `inventory.location` is free text. The agents read it only for reporting.
- The spec's "deck" is the `desk` table. Use `desk` in code.

## MCP tools (Problem 3)

The MCP server in `mcp_server/server.py` has three read-only tools, one for each open ticket. Each is described below by the table it reads, the ticket it unlocks, and why it is the right fit for that ticket.

### 1. `check_inventory_stock(sku, size, qty_needed)`

- **Reads:** `inventory`
- **Unlocks:** ticket 103, the hoodie discount request (Yale AI Club, `CC-HOOD-NAVY` size M, 20 units)
- **Why this tool:** Ticket 103 cannot be decided until someone knows how many size-M hoodies are on hand.
- **Also useful for:** ticket 101, with the same call for `CC-TEE-WHITE` size `S`. It returns 0 on hand against 1 needed, a shortfall of 1.

### 2. `list_open_vendor_invoices(vendor_id?)`

- **Reads:** `invoices`, `vendors`, `desk`
- **Unlocks:** ticket 101, the size-S tee order (Tauhid Zaman)
- **Why this tool:** The size-S tee cannot be restocked until the vendor is free to ship.
- **Also useful for:** ticket 103, which restocks from the same apparel vendor and so is blocked by the same invoice.

### 3. `get_lease_rent_status(lease_id)`

- **Reads:** `leases`, `desk`
- **Unlocks:** ticket 102, the rent notice from Elm City Properties
- **Why this tool:** The rent notice says rent is due in two days, and the team needs to confirm that against the database before acting.

### Notes on the server

- All three tools read the working copy, `data/campus_customs_new.db`, through a read-only connection, so no tool can change data.
- Overdue and due-date results use `desk.date_today`, never the system clock.
- The agent tools added in Problem 5 are listed in `mcp_server/readme.md`.

## Agent team (Problem 5)

Five agents, built with pydantic-ai. Each is defined by one file in `backend/agents/` and one prompt in `backend/prompts/`. All five use `gpt-6-luna` through the Portkey gateway, with `PORTKEY_API_KEY` from the course-root `.env`. Reasoning effort is `none`, which the gateway requires for function tools on this model.

| Agent | File | Prompt | Does | Tools it may call (MCP) |
|---|---|---|---|---|
| Boss | `backend/agents/boss.py` | `prompts/boss.md` | Reads each ticket, routes work, returns the final decision | get_desk, list_tickets, get_ticket, overdue_report, list_approvals, add_ticket_note |
| Inventory | `backend/agents/inventory.py` | `prompts/inventory.md` | Stock by SKU and size, shortfalls, restock vendors, fills orders | get_desk, get_ticket, check_inventory_stock, restock_options, list_vendors, get_pricing, fulfill_order, add_ticket_note |
| Accounting | `backend/agents/accounting.py` | `prompts/accounting.md` | Cash, invoices, margins; prepares payments, POs, discounts | get_desk, get_ticket, get_cash, list_invoices, list_open_vendor_invoices, list_payments, overdue_report, margin_check, get_pricing, list_vendors, list_approvals, request_invoice_payment, request_purchase_order, request_discount_approval, add_ticket_note |
| Facilities | `backend/agents/facilities.py` | `prompts/facilities.md` | Leases, rent due dates, prepares rent payments | get_desk, get_ticket, list_leases, get_lease_rent_status, get_cash, request_rent_payment, add_ticket_note |
| Customer Service | `backend/agents/customer_service.py` | `prompts/customer_service.md` | Drafts customer messages; never sends | get_desk, get_ticket, check_inventory_stock, restock_options, create_draft, add_ticket_note |

Shared pieces:
- `backend/models.py` holds the data types: `AgentName`, `TicketOutcome`, `TicketView`, `AgentReply` (what every agent returns), `DelegationRequest`, `DelegationRefusal`, `BossDecision` (Boss's final call), and `TeamRunResult`.
- `backend/agents/base.py` builds each agent: its model, its prompt, a filtered MCP toolset, a delegation tool for every other agent, and the live event logger.
- `backend/agents/team.py` owns the MCP connection and the ticket loop: it marks the ticket in progress, runs Boss, and writes Boss's decision with `resolve_ticket`. A failure leaves the ticket `blocked` with the error.

### Delegation

Connectivity is full. Every agent has an `ask_<agent>` tool for each of the other four: Boss can ask all four specialists, and each specialist can ask Boss and each other. Two guards keep delegation finite:
- Depth: at most 5 agents in one chain for one ticket.
- Visits: an agent may appear at most twice in one chain.

A refused delegation returns a `DelegationRefusal` with the reason, so the calling agent can finish with what it has rather than fail.

### Rules the team enforces

- The desk date is "today" for every overdue check.
- Cash only goes out. `request_invoice_payment` and `request_rent_payment` refuse if cash cannot cover the amount. The pay step (run only after a human approves) refuses if the balance would go negative.
- Every payment, purchase order, and discount waits for a human. No agent has a tool to approve, reject, pay, or reset.
- A vendor with an open unpaid invoice, or an order in transit, cannot receive a new purchase order.
- Customer messages are drafts only. No tool sends email or contacts a vendor.
- Margin floor: a price must keep at least 25% gross margin, so the floor is cost ÷ 0.75. This is a policy assumption in `mcp_server/shop.py`.

### Live check (Problem 5)

Two tickets were run through the team against the working copy, and the copy was reset afterward:
- **Ticket 102 (rent):** Boss asked facilities. Facilities checked lease 1 ($2,400, due 2026-09-02) and cash ($3,400), requested approval 1, and Boss recorded `awaiting_approval`.
- **Ticket 101 (size S tee):** Boss asked inventory and accounting. Inventory found 0 on hand against 1 needed. Accounting found invoice 501 ($840, 3 days overdue, Bulldog Print Co) and requested approval 2 to pay it. Boss recorded `awaiting_approval`.

Both runs made only requests. No payment or purchase order was executed.

## Decisions from the Problem 6 review

1. **Boss can ask a human a question.** Boss has an `ask_human(ticket_id, question)` tool. It creates a `question` approval that appears on the dashboard. A person answers it through the answer route. The answer is written to the ticket notes, and the ticket reopens for another run. A question can never be approved as a payment. Ticket 103 uses this for the missing target price.
2. **Facilities asks accounting to check cash before any rent request.** Facilities calls `ask_accounting` to confirm cash covers the rent after pending payments. It requests the rent payment only after accounting confirms. This is required.
3. **The late draft gives an ETA and never says "late."** The ticket has no promised date, so the data cannot show an order is late. Customer messages give the expected arrival date from `restock_options` or an approved purchase order.

## Backend routes (Problem 7)

Start from the `backend` folder: `uvicorn main:app --reload --port 8000`. The dashboard calls http://localhost:8000.

- `GET /api/health`: server status, working database name, model, and whether the team is busy.
- `GET /api/tickets`: all tickets, each with `state` set to `open`, `blocked`, or `resolved`, plus overdue and pending-approval counts.
- `GET /api/tickets/{ticket_id}`: one ticket in full, with its linked lease or invoice, stock, drafts, approvals, purchase orders, and notes.
- `POST /api/tickets/{ticket_id}/run`: start the agent team on one ticket in the background (202). Refused while busy (409) or if already resolved (400).
- `GET /api/events?ticket_id=&after=&limit=`: recent agent events, oldest first: what each agent said, the tools it used, delegations, and decisions.
- `GET /api/approvals?status=`: payment, purchase, discount, and question requests, filtered by pending, approved, or rejected.
- `POST /api/approvals/{approval_id}/approve`: a human approves a payment or purchase. This is the only route that changes cash. Refused with 409 if cash cannot cover it. A refused approval sets the ticket to blocked. Any approval starts a run on its ticket automatically.
- `POST /api/approvals/{approval_id}/reject`: a human declines a request, with an optional reason. The ticket runs again automatically.
- `POST /api/approvals/{approval_id}/answer`: a human answers a question Boss raised with `ask_human`. The ticket runs again with the answer.
- `POST /api/tickets/{ticket_id}/notes`: a human adds a note to a ticket, such as a target price. Boss reads it as the person's answer on the next run.
- `GET /api/cash/balance`: current checking balance from `cash_accounts`, with pending payments and what remains after them.
- `POST /api/desk/date`: a human moves the shop's "today" forward. Shipments whose ETA has arrived are received.
- `POST /api/reset`: replace the working copy with the original database. The original file is only read.
- `GET /api/outbox`: pending customer drafts for the Pending outbox section. Nothing in the outbox is sent by the app.
- `POST /api/outbox/{draft_id}/ready`: a person marks a draft ready to send. The app records the decision and does not send the draft.
- `POST /api/outbox/{draft_id}/discard`: a person discards a draft.

## Tables added by the app

These are not in the original database. They are created in the working copy by `ensure_schema` (`mcp_server/shop.py`), and the reset removes them.

- **approvals:** every request a person must decide. Columns: `id`, `kind` (invoice_payment, rent_payment, purchase_order, discount, question), `ticket_id`, `ref_id`, `amount`, `payload`, `summary`, `status` (pending, approved, rejected), `requested_by`, `requested_at`, `decided_by`, `decided_at`, `result`. Why it matters: no cash moves without an approved row here.
- **drafts:** customer messages saved on a ticket. Columns: `id`, `ticket_id`, `channel`, `recipient`, `body`, `status` (always draft), `created_by`, `created_at`. Why it matters: drafts stay on the board and are never sent.
- **purchase_orders:** restock orders. Columns: `id`, `vendor_id`, `sku`, `size`, `qty`, `unit_cost`, `ticket_id`, `approval_id`, `ordered_on`, `eta`, `status` (in_transit, received), `invoice_id`, `received_on`. Why it matters: receipt adds stock and creates the vendor invoice.
- **activity_log:** every agent message, tool call, tool result, delegation, decision, approval, and human note. Columns: `id`, `ts`, `agent`, `ticket_id`, `event`, `detail`. Why it matters: it is the audit trail and feeds the dashboard.
- **tickets, new columns:** `assigned_to`, `resolution` (the team's final summary), `fulfilled_at`.

## MCP tools (full list)

All tools are on the `campus-customs` server (`mcp_server/server.py`). Each agent gets only its allowlist (`backend/agents/*.py`). Approve, reject, answer, desk date, and reset are not tools, so no agent can reach them.

| Tool | Reads or writes | Used by |
|---|---|---|
| check_inventory_stock | inventory | Inventory, Customer Service |
| list_open_vendor_invoices | invoices, vendors, desk | Accounting |
| get_lease_rent_status | leases, desk | Facilities |
| get_desk | desk | all |
| list_tickets | tickets | Boss |
| get_ticket | tickets and linked tables | all |
| overdue_report | invoices, leases, purchase_orders | Boss, Accounting |
| list_approvals | approvals | Boss, Accounting |
| list_vendors | vendors, invoices, purchase_orders | Inventory, Accounting |
| get_pricing | pricing | Inventory, Accounting |
| margin_check | pricing | Accounting |
| restock_options | vendors, inventory, invoices, purchase_orders | Inventory, Customer Service |
| get_cash | cash_accounts, approvals | Accounting, Facilities |
| list_invoices | invoices | Accounting |
| list_payments | payments | Accounting |
| list_leases | leases | Facilities |
| add_ticket_note | tickets, activity_log | all |
| fulfill_order | inventory, tickets | Inventory |
| create_draft | drafts | Customer Service |
| request_purchase_order | approvals | Accounting |
| request_invoice_payment | approvals | Accounting |
| request_rent_payment | approvals | Facilities |
| request_discount_approval | approvals | Accounting |
| ask_human | approvals | Boss |

## The five agents (summary)

| Agent | Its job | What it cannot do |
|---|---|---|
| Boss | Reads each ticket, routes it, and records the final decision (resolved, awaiting_approval, waiting_stock, blocked) | Cannot request money, stock, or discounts directly |
| Inventory | Stock, shortfalls, restock vendors, fulfilling customer orders | Cannot request payments or purchase orders itself |
| Accounting | Cash, invoices, margins; requests payments, purchase orders, and discounts | Cannot approve anything; every request waits for a person |
| Facilities | Leases and rent; asks Accounting to confirm cash before requesting rent | Cannot pay rent |
| Customer Service | Drafts customer messages | Cannot send anything |

Any agent can ask any other agent for help (`ask_<agent>`), within a depth limit of 5 and a limit of two visits per agent per chain.

## API routes (complete)

Routes are in `backend/main.py`. The dashboard calls them at http://localhost:8000. Start from `backend/`: `uvicorn main:app --reload --port 8000`.

- `GET /api/health`, `GET /api/tickets`, `GET /api/tickets/{id}`, `POST /api/tickets/{id}/run`, `POST /api/tickets/{id}/notes`
- `GET /api/events`, `GET /api/approvals`, `POST /api/approvals/{id}/approve`, `POST /api/approvals/{id}/reject`, `POST /api/approvals/{id}/answer`
- `GET /api/cash/balance`, `POST /api/desk/date`, `POST /api/reset`

## The dashboard

`frontend/` is React 19, Vite 8, and TypeScript 5.9. `npm run dev` opens it at http://localhost:5173. It polls the routes above. The board shows three tickets with states Open, Blocked, or Resolved. Each ticket has the team's five agents as cards, a live timeline, a summary of what each agent did, a note box, and the approvals waiting for a decision. The checking balance is always in the top bar. Opening `http://localhost:5173/?ticket=101` selects that ticket directly. The screenshots `output/ticket_101.png`, `ticket_102.png`, and `ticket_103.png` were made this way.

## Safety rules

These are enforced in code, not only in the prompts:

1. **Cash only goes out, and only on a human approval.** Agents create requests. `approve_approval` is the only path that pays, and it runs only from the approve route.
2. **Negative balances are refused.** Payments check balance minus amount before they run, and a refusal sets the ticket to blocked.
3. **No agent can approve, reject, answer, move the desk date, or reset.** These routes are not MCP tools, and no role's allowlist includes them.
4. **No email to customers and no contact with vendors.** The only customer output is `create_draft`, and drafts are stored, not sent.
5. **A vendor with an open unpaid invoice or an order in transit cannot receive a new order.** Enforced by `_vendor_block` when a purchase order is requested and again when it is approved.
6. **Margins have a floor.** A price below cost ÷ 0.75 (a 25% margin) is refused. The floor is a policy assumption in `shop.py`.
7. **Overdue means earlier than the desk date.** The system clock is never used. The desk date moves only forward, and only by a human.
8. **The reference database is never written.** The working copy is `data/campus_customs_new.db`. Opening the reference for writing is refused, and reset copies it only after checking its hash.

## Run record (Problem 9)

- Reset to the original values. Starting checking balance: $3,400.00.
- Fourteen team runs: ticket 101 three times, 102 twice, 103 nine times. Events are in `output/audit_trail.json` (JSON lines, one event per line).
- Seven requests: six approved (three payments, one purchase order, one discount, one answered question) and one declined (purchase order #7). Details are in `output/resolved_tickets.json`.
- Ticket 101: resolved. Ticket 102: resolved. Ticket 103: blocked.
- Checking ends at $152.00. The cash itemization is on the cash tab of `output/desk_tickets.html`.
- Known issue: a decision recorded after an approval executes during a run can overwrite the ticket's status. This happened on tickets 101 and 103 and is described in the reflection tab.

