# Campus Customs agent desk (Homework 5)

A five-agent team that works the Campus Customs shop board: customer orders, rent notices, price overrides, and vendor bills. Boss reads each ticket, delegates to Inventory, Accounting, Facilities, and Customer Service through an MCP server, and makes the final call. A person watches the work on a React dashboard and approves every payment and purchase.

## Layout

```
AI_prompts.md          Log of the prompts used, one section per problem
requirements.txt       Python dependencies
.env.example           Copy to .env and add your PORTKEY_API_KEY (the real .env is never committed)
.gitignore
.mcp.json              Registers the campus-customs MCP server for Claude Code
README.md              This file
data/
  campus_customs.db       Original database. Read-only reference, never written.
  campus_customs_new.db   Working copy. The app reads and writes this file.
mcp_server/
  server.py            MCP server: lookup tools and agent tools
  shop.py              Business rules and the only code that writes to the database
  README.md            What the MCP server is for and its tools
backend/
  main.py              FastAPI routes for the dashboard
  models.py            Shared data types
  agents/              One file per agent (boss, inventory, accounting, facilities,
                       customer_service), plus base.py and team.py
  prompts/             One prompt file per agent
frontend/              React + Vite + TypeScript dashboard
tests/                 Rule tests, route tests, team checks, MCP smoke test
output/
  harness.md           Design document: tables, tools, agents, routes, dashboard, safety rules
  mcp_smoke.json       Evidence that each MCP tool matches the database
  desk_tickets.html    Expected and actual plan for each ticket, cash itemization, reflection
  design.md            Dashboard design
  resolved_tickets.json  Final status, outcome, agent contributions, and approvals per ticket
  resolved_board.html  Board screenshots for tickets 101, 102, and 103
  resolved_board_images/  The three screenshots
  audit_trail.json     Every agent event from the full run (one JSON record per line)
  github_url.txt       The repository URL
```

## Setup (once)

Requirements: Python 3 (built and tested with 3.14) and Node (built and tested with 24).

```bash
# 1. Python environment, from the project root
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# 2. Your API key
cp .env.example .env
# edit .env and set PORTKEY_API_KEY

# 3. Dashboard dependencies
cd frontend && npm install && cd ..
```

## Running the app

Run these in separate terminals, from the project root unless noted.

1. **Start the MCP server.** The agent team starts it for you, so this step is only needed to check the server by hand:
   ```bash
   ./.venv/bin/python -m mcp_server.server
   ```
2. **Start the FastAPI backend.** Run it from the `backend` folder so the dashboard can reach http://localhost:8000:
   ```bash
   cd backend
   ../.venv/bin/uvicorn main:app --reload --port 8000
   ```
3. **Start the React board.** It opens at http://localhost:5173:
   ```bash
   cd frontend
   npm run dev
   ```
   Set `VITE_API_URL` in `frontend/.env` if your backend runs on another port.

## Starting clean (reset the database)

Before a full three-ticket run, put the working copy back to the original values. Either:

- **In the dashboard:** click **Reset database**, or
- **From the command line** (backend running): `curl -X POST http://localhost:8000/api/reset`, or
- **By copying the file** (backend stopped): `cp data/campus_customs.db data/campus_customs_new.db`

The original file is never written. Reset checks its hash first.

## A full three-ticket run

1. Reset the database (above). Checking starts at **$3,400.00**.
2. Open the board and start the team on ticket 101, then 102, then 103. Each run stops at any request that needs a person.
3. Approve, decline, or answer each request in the **Waiting for you** panel. Approving or declining starts a new run on that ticket automatically.
4. Move the desk date to 2026-09-05 when the purchase order should arrive. Only a person can change the desk date.
5. Checking ends at **$152.00** if the run matches the one recorded in `output/`. Ticket 103 ends blocked, because the restock can't be paid with the cash on hand.

Every payment, purchase, and discount is requested by an agent and paid or approved only by a person. Agents cannot approve, reject, answer, change the desk date, or reset the database.

## Tests

```bash
./.venv/bin/python -m pytest -q tests
```

The tests use a temporary copy of the database and make no model calls. `tests/mcp_smoke.py` launches the MCP server exactly as `.mcp.json` describes and checks each lookup tool against the database, so run it on a reset database.

## Model and gateway

All agents use `gpt-6-luna` through the Portkey gateway, with `PORTKEY_API_KEY` from `.env`. The gateway accepts function tools on this model only with reasoning effort set to `none`, so the agents run that way.

## Known limitations

- Desk date and cash are simulated. The homework has no revenue, so checking can only go down.
- Ticket 103 can't resolve with a restock on this budget. It ends blocked, and the reflection in `output/desk_tickets.html` explains why.
- Model calls cost money. Each human decision starts a run, so a busy session uses more of the budget.
