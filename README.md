# Campus Customs agent desk (Homework 5)

A five-agent team runs the Campus Customs shop board. Boss reads each ticket and delegates to Inventory, Accounting, Facilities, and Customer Service through an MCP server, then makes the final call. A person watches on a React dashboard and approves every payment and purchase. Agents can only request; they never pay, approve, or send email.

## Layout

```
hw5/
├── AI_prompts.md        Prompt log, one section per problem
├── requirements.txt     Python dependencies
├── .env.example         Copy to .env and add your PORTKEY_API_KEY
├── .gitignore
├── .mcp.json            Registers the campus-customs MCP server
├── README.md
├── data/
│   ├── campus_customs.db       Original database (never written)
│   └── campus_customs_new.db   Working copy the app uses
├── mcp_server/
│   ├── server.py        MCP server (tools)
│   ├── README.md
│   └── shop.py          Business rules; the only code that writes the database
├── frontend/            React + Vite + TypeScript dashboard
├── backend/
│   ├── main.py          FastAPI routes
│   ├── models.py        Shared data types
│   ├── prompts/         One prompt per agent
│   ├── agents/          The five agent definitions and the team loop
│   └── test_*.py        Tests; mcp_smoke_test.py checks the MCP tools
└── output/
    ├── harness.md       Design: tables, tools, agents, routes, dashboard, safety
    ├── mcp_smoke.json   MCP tool check against the database
    ├── desk_tickets.html  Plan, actual results, cash, and reflection per ticket
    ├── design.md        Dashboard design
    ├── resolved_tickets.json
    ├── resolved_board.html and ticket_101/102/103.png
    ├── audit_trail.json every agent event from the runs
    └── github_url.txt
```

`backend/agents/` and `mcp_server/shop.py` are not in the assignment's sketch, but the code needs them. `frontend/` holds the usual Vite project files.

## Setup (macOS or Linux)

You need Python 3 (built and tested with 3.14) and Node 24 (built and tested with 24).

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then put your own PORTKEY_API_KEY in .env
cd frontend && npm install && cd ..
```

## Running the app

Run each step in its own terminal, from the project root unless noted.

1. **Start clean (optional):** `cp data/campus_customs.db data/campus_customs_new.db`. The dashboard's Reset button does the same.
2. **MCP server (optional check):** `./.venv/bin/python -m mcp_server.server`. The backend starts it for you, so this only checks it by hand.
3. **Backend:** `cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000`
4. **Dashboard:** `cd frontend && npm run dev` opens http://localhost:5173.

## Checking the install (no model calls)

```bash
./.venv/bin/python -m pytest -q backend
./.venv/bin/python backend/mcp_smoke_test.py
```

Expect `33 passed` and three `MATCH` lines. Run the smoke test on a reset database.

## A full three-ticket run

1. Reset the database (step 1 above). Checking starts at $3,400.00.
2. Start the team on ticket 101, then 102, then 103 from the board.
3. Decide each request in **Waiting for you**. Approving or declining starts a new run on that ticket.
4. Move the desk date to 2026-09-05 when the purchase order should arrive. Only a person can change the desk date.

## Expected results

- **Ticket 101:** pays invoice 501 ($840.00) after approval, requests an $8.00 purchase order, and resolves once the tee is fulfilled.
- **Ticket 102:** pays rent ($2,400.00) after approval and resolves. The next due date moves to 2026-10-02.
- **Ticket 103:** ends blocked. A $264.00 restock cannot be paid with the cash on hand.
- **Ending checking:** $152.00.

Agent wording and run counts will differ between runs. Approvals and the ending balance should match. The original run is recorded in `output/`.

## Tools and models

All agents use `gpt-6-luna` through the Portkey gateway, with `PORTKEY_API_KEY` from `.env`. The gateway accepts function tools on this model only with reasoning effort set to `none`, so the agents run that way. Each model call costs money, and each human decision starts a run.

## Limits

- Desk date and cash are simulated. The homework has no revenue, so checking can only go down.
- Ticket 103 cannot resolve with a restock on this budget. It ends blocked.
- The app runs on macOS or Linux, and the backend needs port 8000.
