# AI Prompts Log: Homework 5

This file logs what I typed into the vibe coder while working on Homework 5. Each problem gets its own section. Prompts are copied word for word, typos included. Each message is labeled with the problem number and title it belongs to. Each follow-up either corrects an earlier prompt (marked **What was lacking**) or is marked **Not a correction**.

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

### Follow-up 2: Move the message to Problem 1

> NO the previous message should go under problem 1.

**What was lacking:** the message was not placed under Problem 1.

### Follow-up 3: Rename and label

> The current "follow up 2" prompt should be under the Problem 1 section because I'm now telling you how to build the homework assignment and we're doing with the context to this homework assignment. rename prompt 1 to introduction or background or something. I will say the problem number and the title before each message moving forward.

**What was lacking:** the prompt 1 title was too specific, and the labels did not follow the instruction to put this message under Problem 1.

### Follow-up 4: Listen to the previous message

> you didn't listne to anything i said in the previous message.

**What was lacking:** the earlier changes did not follow the instructions in the message before it.

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

**What was lacking:** the first prompt did not say that port 8000 was taken by another project's server, so the backend could not start on that port.

### Follow-up 2: Open the dashboard

> open the dashboard

**Not a correction.**

---

## Problem 9: Resolve the tickets

### Prompt 1: Reset, run all three tickets, and document the results

> problem 9 is called resolve the tickets. before testing the agents on a full run over the three tickets, reset the working database (data/campus_customs_new.db) so we can start clean. note the starting checking balance. then run all three tickets on the board until each ticket is resolved. open output/desk_tickets.html from problem 6 and on each ticket tab, fill in the actual section from this run: which agents worked, what was delegated, and which tools they used. keep the expected section so we can compare the two. on the cash tab of the same desk_tickets.html, itemize the moeny: starting checking balance (after the reset), for each ticket, how cash changed when that ticket resolved, and why (which pay /purchase amount dollar amount), ending checking balance - must match cash_accounts in the working database. Wrong cash math loses points so please ensure these are correct especially when the board shows every ticket resolves. also save output/resolved_tickets.json for each ticket: id, final status, short outcome, what each agent contributed, and all human approvals, output/resolved_board.html should be a page we can double click with a screenshot of the react board for each resolved ticket 101 102 and 103. append real runs to output/audit_trail.json finish harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules

### Follow-up 1: Approve the requests

> approved everything

**Not a correction.**

### Follow-up 2: Margin wording and the invoice question

> it should say this is below the 29.33 margin level - want to re-edit this to 29.33? for 103 and then I can approve that, but then it gets stopped there because of the restock fee being more than the checking account. the t invoice from receipt also wasnt recorded against teh checking account -- why?

**What was lacking:** the first answer said the price was below the floor without giving the margin percentage, and it did not explain that an invoice only exists after a shipment is received.

### Follow-up 3: Price choice and business cadence

> 29.33 for 103 and what's the typical cadence a business follows in an instance similar to this?

**Not a correction.**

### Follow-up 4: Blocked tickets

> if an action is blocked, the ticket should record blocked and not remain "open"

**What was lacking:** blocked tickets were shown as open, and a refused payment left the ticket unchanged.

---

### Follow-up 5: Build the ask

> yes build the ask, move to accommodate inventory arrival

**What was lacking:** there was no way for a person to give the team a price, and the desk date had not moved for the inventory arrival.

### Follow-up 6: Approve the discount

> approved it

**Not a correction.**

### Follow-up 7: Pay and restock

> pay then request restock

**Not a correction.**

### Follow-up 8: Decisions trigger runs

> i declined it in the system so is there a way to make my responses automatically trigger the agents to act with that instead of having to come back here to tell you what I did?

**What was lacking:** decisions made on the dashboard did not start a run, so the team could not act on them without a message from you.

---

## Problem 10: Reflection

### Prompt 1: Fill in the Reflection tab

> Problem 10 is called Reflection. Open desk_tickets.html and fill in the Reflection tab. I need you to edit my answers to be thorough and detailed, but help me evaluate: the performance of the agents on each ticket and why I think that? How each ticket compared to the expected that we wrote at the beginning, what could have been simpler as one agent with tools and why, three new problems that campus customs might face that this agent could solve with the tools built, and three new problems campus customs might face that this agent team could not solve with the tools wer built, and explain what we would need to add in order to solve these. tie every answer to this app and the three tickets we ran - use the ticket tabs and cash tab on the same page as our evidence. do not let this essay be generic AI stuff.

---

### Follow-up 1: Finish the Problem 9 deliverables

> yes finish those now

**What was lacking:** the Problem 9 deliverables (resolved files, board page, and harness) were not finished.

### Follow-up 2: Stale status and screenshots

> Fix the stale status bug and where can I validate the screenshots are located?

**What was lacking:** the stale-status bug was known but not fixed, and the screenshot locations were not given.

---

## Problem 11: Submit to GitHub

### Prompt 1: Publish the repository

> problem 11 is called submit to github. Push this code to a public github repository so graders acna clone it. I'll submit the repo url as my submission, and it should also be in output/github_url.txt . Do not push the real env to the github repo. do include both databsed files under data/ so graders can run the app easily. read the attached screenshot for the expected file layout and note that README should explain, copy original DB to the working copy when we need a clean run, start mcp server, start fastAPI backend, start the react board, and reset the db before a full three-ticket run.

---

## Testing completed product

### Follow-up 1: Another test run

> can we run another test on this and have you show me what's happening

**Not a correction.**

### Follow-up 2: Pause and add a pending outbox

> pause. we need an outbox of pending emails to send to customers about their orders and I need to see that on my dashboard under the approvals area

**Not a correction.**

### Follow-up 3: Name and sending rule

> maybe make the title pending outbox and yes, do not send any emails.

**What was lacking:** the outbox title and the rule against sending were not specified.

### Follow-up 4: Triple-check the work

> cna you triple check adherence to the information i submitted throughout all prompts submitted thus far? be thorough and flag any potential issues or things to fix. this is essential to do well on this assignment.

**Not a correction.**

### Follow-up 5: Fix the flagged items

> 1. do this. 2. this ticket can be resolved by being blocked, right? not sure how to proceed since it's not supposed to be resolved. 3. complete the audit trail. 4. fix this. 5. add all runs and explanations of why additional comments were needed whenever that was the case. anything after problem 11 can fall under testing completed product. 6.  I just spoke about. 7. do this correctly. 8. please condense these to be as concise as possible.

**What was lacking:** the earlier review had open items that were unclear or unfinished.

### Follow-up 6: How to do item 7

> how do i do 7

**Not a correction.**

### Follow-up 7: Repeatable for a TA

> is that going to be easily repeatable for a TA to download from the github repo to recreate? we should optimize for that

**What was lacking:** the steps were not written so a TA could reproduce them from the repo alone.

### Follow-up 8: Match the expected layout

> okay we need to make this as easy to grade as possible. optimize it so that if a TA downloaded this project from a repo, they have their own portkey, and it follows the layout above
[Image: the expected file layout (hw5/ tree) and the README requirements]

**What was lacking:** the project did not match the expected file layout, and the README did not cover the steps the assignment lists.

### Follow-up 9: Flow and presentation

> okay now the tickets aren't flowing naturally and I'm not being presented with stuff as I once was. can we fix this?

**What was lacking:** runs could start or stay queued without a visible reason, and a server restart could leave a ticket stuck in progress.

