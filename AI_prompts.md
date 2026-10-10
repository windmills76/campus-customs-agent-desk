# AI Prompts Log: Homework 5

This file logs what I typed into the vibe coder while working on Homework 5. Each problem gets its own section. Prompts are copied word for word, typos included. Each message is labeled with the problem number and title it belongs to. Follow-ups are marked with the sentence on what the earlier prompt lacked.

---

## Problem 1: Vibe coder prompts

### Prompt 1: Introduction and background

> Homework 5 is about building a multi agent operation where the agentic team we build runs the shop. open tickets land on a baord - cusotmer orders, rent, unpaid bills, discount requests, whatever the shop has to handle. you need to build a MCP server, a fastAPI backend with multiagent team, and a react dashbord so a human can watch the agents at work and approve requests. the agents we are building are Boss (reads each ticket, decides who should work on it, and makes the final call), inventory (checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock), accounting (watches cash and invoices, checks margins, and  prepares payments or purchase orders for human approval), facilities (handles the shop space side like leases, rent, etc.) and customer service (drafts messages for customers). unzip the most recent data.zip file in my downloads folder into the homework 5 folder. tables should include deck, tickets, inventory, pricing, vendors, leases, cash_acocunts, payments, and invoices. YOu will build tools to update the databse as tickets get resolves. Make a copy of the database file called data/campus_customs_new.db and point your MCP server and backend at that working copy. keep campus customs.db untouched so that you can reset when we want to restart resolving the tickets. RULES: Desk.date_today is "today" for the shop. use this date to determine what is overdue. vendor lead times come from the vendors table. a vendor will not ship new product while they still have an open unpaid invoice. Human approval is required for any payments. When and if a payment is made, this must be reflected in the relevant table. if there is not enough cash, the pay tool must refuse - negative balances are prohibited. cash only goes out in this homework (no revenue model so no money comes in). Before a full run to resolve the tickets, make sure to reset the database to the original values. and do not email customers or call real vendors. drafts stay on the board. Final submission will be a public github repo.

### Follow-up 1: Hold construction

> we haven't really started building yet so you can hold on that construction. that was context for you to reference as we build.

**What the first prompt lacked:** the stop-or-start instruction. I should have asked, or waited, before creating files. The follow-up made clear the description was reference material only.

### Prompt 2: Create the prompt log

> Problem 1 is called vibe coder prompts. create ai_prompts.md and keep it updated as you work. this file is the log of what I type into this vibe coder. Create one section for each problem while you execute the problems. Each section must include the problem number and title, at least one prompt typed in the wording I use, and one follow-up prompts if needed to correct something with an additional sentence on what was lacking after the first.

---

## Problem 2: Study the campus customs database

### Prompt 1: Study the database and start the harness

> lets move on for now. problem 2 is called sutdy the campus customs database. OPen data/campus_customs.db and look through every table and its fields. Copy the original file to data/campus_customs_new.db - later problems update this working copy. Study the three open tickets so that you see how they link to other tables. Start output/harness.md for each table, list the fields and one short line on why that table matters for the agents. you will keep growing this harness file in later problems.

---

## Problem 3: Build the MCP server

### Prompt 1: Build the MCP server with three tools

> Problem 3 is called build the MCP server. Write an MCP server in mcp_server/ using FastMCP. It will talk to data/campus_customs_new.db you do not need to connect or run it in this problme. Every agent in this hopmework uses the tools in this mcp server. we will add more tools to it later, for now write three ttools you know you will need for the tickets in the database. Kepe the names clear. Never invent any data, only use information in the database. in output/harness.md, list each of the tree mcp tools. for every tool, include: which table it reads, which ticket it help unlock (101, 102, or 103) and one sentence on why that tool is the right one for that ticket. vague lines like read inventory are not acceptable -- provide thorough explanations of fit. Also add a short mcp_server/readme.md file that explains what the mcp server is for, which databnse file it uses, and the three tools it has.

---

## Problem 4: Add the MCP server to vibe coder and test each tool

### Prompt 1: Connect the MCP server and test each tool

> problem 4 is called "add the mcp serve to vibe coder and test each tool". Add the MCP serve to this project so that you can call all of the tools. save the connection json text in .mcp.json at the project root. with these connected, test each of the three mcp tools. save the evidence in output/mcp_smoke.json. For every tool, include: 1) the prompt you asked the vibe coder, 2) the tool name, and 3) the tool output (must match values in data/campus_customs_new.db)

---

## Problem 5: Build the agent team and grow the MCP tools

### Prompt 1: Build the five-agent team and expand the MCP tools

> Problem 5 is called build the agent team and grow the mcp tools. Build the agentic team for campus customers using pydanticAI: boss, inventory, accounting, facilities, and custoemr service. Include prompts, models, and agent loops so they can delegate work toe ach other with full connectivity. Put the agent prompts in backend/prompts/ and make one file per agent. put data types in backend/models.py and the agent files under backend/ and ensure that the five roles are clear. use the portkey_API_key and gpt-6-luna only for every agent. you should already have the sop rules that the agent needs, but add detail to it to cover all aspects of the agent's needs.

---

## Problem 6: Plan the three tickets

### Prompt 1: Write the expected plan for each ticket

> problem 6 is called plan the three tickets. before wiring the backend, write down what we expect to the team to do on each open ticket. build output/desk_tickets.html - a page I can double clcik with one tab per ticket (101,102,103). Add empty cash and reflection tabs for later problems (leave blank or with a "coming later" note for now. On each ticket tab, fill an expected section only (leave room for an actual section we will fill after we run the agents). For each ticket's expected section, I need you to tell me how to read them so that I can say what I expect the agents to do in order and then you can tell me if that's a fair assumption or if we should alter the thought to include other agents. We need ot have who the boss calls first, all agent delegations expected, and which MCP tools we expect that run to use.

### Prompt 2: My expected order for tickets 101 and 102

> 102 - expect boss to call facilities, then accounting to make sure enough money to pay rent, then boss to pose it to the human, human approval would trigger accounting to pay that then facilties would receive payment of it, and then boss decision would be resolved. 101- boss would receive request, call inventory, inventory would say need to order more, boss goes to accounting to ask if able to order more (no outstanding POs). requests approval to oay invoice 501 for 2400. request sent back to boss to send to human. Then boss sends reques tot inventory now that we are expecting to receive more inventory with that sku., boss then goes to accounting. boss then asks human to approve request to buy sku. eta should be written in and then sent to inventory to fulfill the order. boss then sends customer service a draft to send the customer that the order will be late due to inventory inssues. for 103, you can keep the expected outcome that's currently there.

### Prompt 3: Answers to the three open questions

> answering questions in problem 6: 1. Boss should have a tool to ask human a question. 2. ask accounting to check cash. 3. for the late draft, we could just provide an ETA without saying "late".

---

## Problem 7: Backend routes

### Prompt 1: Add the backend routes

> problem 7 is called backend routes. the react frontend dashboard (next problem) needs a backend it can call. in backend/main.py, use fastAPI and add routes that do the following: return the three tickets and whether each is open or resolves, take a ticket id and run the agent team on that ticket, return recent agent events - what each agent said and which tools they used - so the board can refresh, approve a payment or purchase after a human clicks approve (agents should only prepare the pay; this route is what actually changes cash)m reutn the current checking balance from cash_accounts, and reset the database to the original values when we want to try a fresh run. from the backend folder, start the server with: uvicorn main:app --reload --port 8000, because this turns on the backend at http://localhost:8000 so the frontend dashboard can call those routes. in output/harness.md, list each route in one line (what url/ what it does).

---

## Problem 8: Agent dashboard

### Prompt 1: Build the frontend dashboard

> Problem 8 is called Agent dashboard. build the frontend dashboard in frontend/ with react + vite + type script. the page should call the routes we built in problme 7. at a minimum, the board should: 1) list all three tickets, 2) let a human pick one ticket and start the agent team on it, 3) show each agent and what they are saying/doing while the ticket runs, 4) mark a ticket resolves when the run finishes, 5) show a short summary of what each agent did on that ticket, 6) let a human approve a pay or purchase when asked, 7) show the checking balance (it should drop after an approved pay). Make the dashboard look good - the layout and feel should be elevated, cohesive, fast, and modern. I want the apple inc aesthetic with more blue across the website because we need to make this attractive to actual humans using this platform to run the campus customs site. the front end should talk to the backend at http://localhost:8000. on the backend, the vite page origin (usually http://localhost:5173 should connect directly to this and can call these routes. start the board with: npm run dev to open the react desk in my browser so that I can pick tickets and watch agents. write output/design.md with what I said to make the dashboard look like (layout, how the agents read differently, how resolves tickets and cash show up) and why - included the creative choices that make it feel special and something hymans would actually enjoy using. feel free to add your own research and thoughts ehre ontop of what i've already said on this matter.

### Follow-up 1: Stop the other server

> you can stop it

### Follow-up 2: Open the dashboard

> open the dashboard

---

## Problem 9: Resolve the tickets

### Prompt 1: Reset, run all three tickets, and document the results

> problem 9 is called resolve the tickets. before testing the agents on a full run over the three tickets, reset the working database (data/campus_customs_new.db) so we can start clean. note the starting checking balance. then run all three tickets on the board until each ticket is resolved. open output/desk_tickets.html from problem 6 and on each ticket tab, fill in the actual section from this run: which agents worked, what was delegated, and which tools they used. keep the expected section so we can compare the two. on the cash tab of the same desk_tickets.html, itemize the moeny: starting checking balance (after the reset), for each ticket, how cash changed when that ticket resolved, and why (which pay /purchase amount dollar amount), ending checking balance - must match cash_accounts in the working database. Wrong cash math loses points so please ensure these are correct especially when the board shows every ticket resolves. also save output/resolved_tickets.json for each ticket: id, final status, short outcome, what each agent contributed, and all human approvals, output/resolved_board.html should be a page we can double click with a screenshot of the react board for each resolved ticket 101 102 and 103. append real runs to output/audit_trail.json finish harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules

### Follow-up 1: Approve the requests

> approved everything

### Follow-up 2: Margin wording and the invoice question

> it should say this is below the 29.33 margin level - want to re-edit this to 29.33? for 103 and then I can approve that, but then it gets stopped there because of the restock fee being more than the checking account. the t invoice from receipt also wasnt recorded against teh checking account -- why?

### Follow-up 3: Price choice and business cadence

> 29.33 for 103 and what's the typical cadence a business follows in an instance similar to this?

### Follow-up 4: Blocked tickets

> if an action is blocked, the ticket should record blocked and not remain "open"

---

## Problem 10: Reflection

### Prompt 1: Fill in the Reflection tab

> Problem 10 is called Reflection. Open desk_tickets.html and fill in the Reflection tab. I need you to edit my answers to be thorough and detailed, but help me evaluate: the performance of the agents on each ticket and why I think that? How each ticket compared to the expected that we wrote at the beginning, what could have been simpler as one agent with tools and why, three new problems that campus customs might face that this agent could solve with the tools built, and three new problems campus customs might face that this agent team could not solve with the tools wer built, and explain what we would need to add in order to solve these. tie every answer to this app and the three tickets we ran - use the ticket tabs and cash tab on the same page as our evidence. do not let this essay be generic AI stuff.

