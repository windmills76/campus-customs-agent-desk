"""Checks on the agent team that need no model calls: every role's tools exist on the MCP server,
no role can reach a human-only action, and every agent can delegate to every other agent."""

import asyncio

from backend.agents.base import MAX_DEPTH, MAX_VISITS_PER_AGENT, check_delegation
from backend.agents.team import ROLE_SPECS, AgentTeam
from backend.models import SPECIALIST_NAMES

HUMAN_ONLY = {"approve_approval", "reject_approval", "set_desk_date", "reset_working_copy", "pay_invoice"}


def test_every_role_tool_exists_on_the_mcp_server(shop_db):
    team = AgentTeam()

    async def server_tools():
        async with team.mcp:
            return {tool.name for tool in await team.mcp.list_tools()}

    available = asyncio.run(server_tools())
    for spec in ROLE_SPECS:
        missing = set(spec.tools) - available
        assert not missing, f"{spec.name} lists tools the server does not expose: {missing}"


def test_no_role_can_reach_human_only_actions():
    for spec in ROLE_SPECS:
        assert not HUMAN_ONLY & set(spec.tools), spec.name


def test_full_delegation_connectivity():
    team = AgentTeam()
    everyone = ["boss", *SPECIALIST_NAMES]
    for caller in everyone:
        targets = {name for name in everyone if name != caller}
        delegate_tools = {t for t in team.agents[caller]._function_toolset.tools if t.startswith("ask_")}
        assert delegate_tools == {f"ask_{t}" for t in targets}, caller


def test_delegation_guards_stop_loops_and_depth():
    assert check_delegation(["boss"], "inventory") is None
    assert check_delegation(["boss", "inventory"], "accounting") is None
    assert check_delegation(["boss", "inventory", "inventory"], "inventory") is not None  # visit limit
    chain = ["boss", "inventory", "accounting", "facilities", "customer_service"][:MAX_DEPTH]
    assert check_delegation(chain, "boss") is not None  # depth limit
    assert MAX_VISITS_PER_AGENT == 2
