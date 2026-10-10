# Agent desk: design

This is the design for the Campus Customs agent dashboard (`frontend/`). It covers what I asked for, why, and the choices that make it feel built for the people who run the shop.

## What I asked for

- **Look and feel.** Apple-inspired: elevated, cohesive, fast, and modern. More blue across the whole site, so it reads as one brand.
- **Audience.** Real people who run the shop, not engineers. The page should make them feel in control and make the agents' work easy to follow.
- **Behaviour.** The board must list all three tickets, let a person pick one and start the agent team on it, and show each agent and what it is saying or doing while the ticket runs. It must mark a ticket resolved when the run finishes, show a short summary of what each agent did, let a person approve a payment or purchase when asked, and show the checking balance, which must drop after an approved payment.
- **Run.** `npm run dev` should open the desk in the browser. The desk talks to the backend at http://localhost:8000.

## Layout

Three columns, read left to right in the order the work happens:

1. **Board (left).** The three tickets as cards. Each card shows its number, subject, requester, a state pill (Open or Resolved), the current status in plain words ("Waiting on stock"), and flags for overdue items and requests waiting for approval. The selected card gets a blue ring.
2. **Ticket (centre).** A blue hero block with the ticket's subject, requester, item, and a single primary action: "Start agent team." Below it:
   - **The team.** Five agent cards in a grid.
   - **Live activity and What each agent did.** A timeline of the current run, beside a summary of each agent's work.
   - **Requests on this ticket.** Every payment, purchase, discount, and question tied to the ticket, with its status.
3. **Waiting for you (right).** Pending requests across the board, with this ticket's requests first. This is the human's inbox.

The cash balance sits in the top bar, always visible, in a blue card.

## How the agents read differently

Each agent has its own colour and a role line, so the five are easy to tell apart in a glance:

| Agent | Colour | Role line |
|---|---|---|
| Boss | deep navy | Reads the ticket, routes it, makes the call |
| Inventory | Apple blue | Stock, shortfalls, restock vendors |
| Accounting | teal-blue | Cash, invoices, margins, requests |
| Facilities | indigo | Leases and rent |
| Customer Service | light cyan | Drafts customer messages |

A card has three states:

- **Idle.** Faded, "Not on this ticket yet."
- **Working.** Lifted, with a coloured outline, a breathing "Working" badge, and a shimmering speech bubble. The bubble says what the agent is doing right now, such as "Using check_inventory_stock" or "Asking Accounting."
- **Done.** Solid, with a green "Done" badge. The bubble shows the agent's last reply in its own words.

The timeline mirrors the cards. Each agent's messages are speech bubbles in its colour. Tool calls appear as dark monospace chips, so a person can see exactly which tool was used. Tool results are folded away under "Result," so the timeline stays readable. Delegations show as "Asking <agent>." The final decision appears as a highlighted card.

## How resolved tickets show up

- While a run is active, the ticket card reads "Team working…" with a blue status line, and the top bar shows the team as busy with a moving shimmer.
- When the run ends, a toast confirms it ("Run finished: ticket #101 is awaiting approval"). The card updates to its final state.
- A **resolved** ticket gets a green pill, a green banner with the team's decision, and the start button is replaced by a disabled "Resolved" label.
- A ticket that is waiting on a person shows "Awaiting approval," which is different from resolved. The distinction matters: it tells the person whether anything is left for them to do.

## How cash shows up

- The checking balance is always in the top bar, in a blue card, so a person can see the money position at all times.
- The number eases to its new value over about a second, rather than snapping. A small chip shows the amount that went out ("−$840.00"), which fades after a few seconds.
- Underneath the balance, the card shows what is still available after payments awaiting approval. A person can see the cost of a pending request before approving it.
- Money requests are the only place a person can approve something that spends cash. The Approve button turns into "Confirm $840.00 out of checking?" with a Back option. This is deliberate: a click should not spend money by accident.

## Creative choices

- **Two-step money approvals.** Approving a payment takes a second, explicit confirmation that names the amount. Decisions that cost nothing do not need it.
- **Questions from Boss get an answer box.** When Boss asks a person something, such as a target price for a discount, the request has a text field instead of buttons. The answer goes straight back to the ticket.
- **Agent colours from one blue family.** The agents are distinct, but they all sit in the brand's blues. The page feels like one product.
- **Glass top bar and blue hero.** The top bar is translucent over the background, and each ticket opens with a full-width blue hero. Blue carries the brand without making the page busy.
- **Quiet motion.** Cards rise in on load, the working agent lifts and shimmers, and the balance eases. Everything respects the system's reduced-motion setting.
- **Plain-language status.** "Waiting on stock" and "Awaiting approval" replace raw codes such as `waiting_stock`. Money uses US dollars with cents.
- **Empty states that explain.** "Pick a ticket" and "All clear" tell a person what to do next, rather than showing blank space.

## Research and my own thoughts

I have not run a user study. I did not browse for research, so the points below are from general design practice rather than sources I checked. Here is my reasoning beyond what you asked for.

- **Show the work, not the logs.** Non-technical users trust a system they can follow. Speech bubbles and plain labels let them follow the agents without reading raw JSON. Tool names stay visible, so an expert can still check a claim.
- **Make waiting feel active.** A running job with no feedback feels broken. The working state, shimmer, and live timeline show progress, so people will wait without refreshing.
- **Separate "done" from "needs you."** The most likely mistake is a person thinking a ticket is finished when a human decision is still needed. The Resolved and Awaiting-approval states look different on purpose.
- **Guard money, but not everything.** Two steps for money protects against accidents without slowing routine work.
- **Hierarchy by position.** Left to right follows the workflow: pick, watch, decide. The primary action sits in the hero, where the eye lands after choosing a ticket.
- **Things I would test next.** Whether the balance animation is noticed or distracting; whether five agent cards are too many on a small laptop; whether the approvals column should sit in a drawer on narrow screens. These would need real users.

## Open items

- The page is built and type-checks, but I could not look at it in a browser in this session (the Chrome extension was not connected). Open it with `npm run dev` and check the layout yourself.
- The backend is currently on port 8050 in my tests, because port 8000 is held by another project. The desk calls http://localhost:8000 by default. Set `VITE_API_URL` to point elsewhere.
