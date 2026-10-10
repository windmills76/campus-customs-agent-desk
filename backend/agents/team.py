"""The Campus Customs agent team: one MCP connection, five agents, and the ticket run loop.

Flow for one ticket:
1. The backend marks the ticket in_progress.
2. Boss reads the ticket and may delegate to any specialist through ask_<agent> tools.
   Specialists may delegate to Boss or to each other, within the depth and visit limits.
3. Boss returns a BossDecision. The team writes it to the ticket with resolve_ticket.
4. Any failure leaves the ticket blocked with the error, never stuck in_progress.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from datetime import datetime
from typing import Any

from pydantic_ai import UsageLimits
from pydantic_ai.mcp import MCPServerStdio

from backend.agents.accounting import SPEC as ACCOUNTING
from backend.agents.base import (
    REQUEST_LIMIT,
    ROOT,
    AgentSpec,
    TeamDeps,
    build_agent,
    make_event_logger,
)
from backend.agents.boss import SPEC as BOSS
from backend.agents.customer_service import SPEC as CUSTOMER_SERVICE
from backend.agents.facilities import SPEC as FACILITIES
from backend.agents.inventory import SPEC as INVENTORY
from backend.models import AgentName, AgentReply, BossDecision
from mcp_server import shop

ROLE_SPECS: tuple[AgentSpec, ...] = (BOSS, INVENTORY, ACCOUNTING, FACILITIES, CUSTOMER_SERVICE)


class AgentTeam:
    def __init__(self) -> None:
        self.model_name = "gpt-6-luna"
        self.mcp = MCPServerStdio(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
            env={"CAMPUS_DB_PATH": str(shop.working_db_path()), "PATH": os.environ.get("PATH", "")},
            cwd=str(ROOT),
            timeout=30,
        )
        titles = {spec.name: spec.title for spec in ROLE_SPECS}
        self.agents = {spec.name: build_agent(spec, self.mcp, titles) for spec in ROLE_SPECS}
        self._stack = AsyncExitStack()
        self.lock = asyncio.Lock()
        self.busy = False
        self.current_ticket: int | None = None
        self.queue: list[int] = []

    # --- connection -------------------------------------------------------

    async def start(self) -> None:
        await self._stack.enter_async_context(self.mcp)

    async def stop(self) -> None:
        await self._stack.aclose()

    # --- agent runs -------------------------------------------------------

    async def run_agent(
        self,
        name: AgentName,
        prompt: str,
        ticket_id: int,
        chain: list[AgentName],
        output_type: Any = AgentReply,
    ) -> Any:
        """Run one agent on one request. Used for Boss's top-level run and for every delegation."""
        agent = self.agents[name]
        deps = TeamDeps(ticket_id=ticket_id, chain=chain, team=self)
        result = await agent.run(
            prompt,
            deps=deps,
            output_type=output_type,
            event_stream_handler=make_event_logger(name, ticket_id),
            usage_limits=UsageLimits(request_limit=REQUEST_LIMIT),
        )
        output = result.output
        if isinstance(output, AgentReply):  # what the agent said, for the dashboard's agent cards
            shop.log_event(name, ticket_id, "message", output.answer[:2000])
        return output

    async def run_ticket(self, ticket_id: int) -> None:
        """Run the whole team on one ticket. The ticket always ends in a decided status."""
        async with self.lock:
            self.current_ticket = ticket_id
            started = datetime.now().isoformat(timespec="seconds")  # same clock format as approvals.decided_at
            try:
                shop.set_ticket_status(ticket_id, "in_progress", agent="boss", assigned_to="boss")
                desk = shop.get_desk()
                ticket = shop.get_ticket(ticket_id)
                prompt = (
                    f"Shop desk date (today): {desk['date_today']}.\n"
                    f"Ticket #{ticket_id} (JSON):\n{json.dumps(ticket, default=str)}\n\n"
                    "Decide which specialist(s) should act and ask them. Read their replies, check approvals if needed, "
                    "then return your BossDecision."
                )
                decision: BossDecision = await self.run_agent(
                    "boss", prompt, ticket_id, ["boss"], output_type=BossDecision
                )
                decided_mid_run = shop.approvals_decided_since(ticket_id, started)
                if decided_mid_run:
                    # A person decided something while the team was working, so this decision may be out of date.
                    # Reopen the ticket and run it again instead of recording a stale status.
                    shop.reopen_ticket(ticket_id, f"approval(s) {decided_mid_run} decided during the run; running again")
                    self.queue.append(ticket_id)
                else:
                    shop.resolve_ticket(ticket_id, decision.outcome, decision.summary, agent="boss")
            except Exception as exc:  # keep the board honest if a model call or the database fails
                shop.log_event("system", ticket_id, "error", repr(exc)[:500])
                shop.resolve_ticket(ticket_id, "blocked", f"Run failed: {exc!r}"[:500], agent="system")
            finally:
                self.current_ticket = None

    def request_run(self, ticket_id: int) -> None:
        """A human decision on a ticket starts a run on it. If the team is busy, the ticket waits in the queue."""
        if ticket_id in self.queue or ticket_id == self.current_ticket:
            return
        if self.busy:
            self.queue.append(ticket_id)
        else:
            self.launch([ticket_id])

    def launch(self, ticket_ids: list[int]) -> None:
        """Mark the team busy right away (so a second request is refused), then run in the background."""
        self.busy = True
        self.queue = list(ticket_ids)
        asyncio.get_running_loop().create_task(self.run_queue())

    async def run_queue(self) -> None:
        """Run queued tickets one at a time, so writes and agent reasoning never overlap."""
        try:
            while self.queue:
                await self.run_ticket(self.queue.pop(0))
        finally:
            self.queue = []
            self.busy = False
