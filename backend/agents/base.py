"""Shared machinery for the five Campus Customs agents.

Every agent is built the same way:
- one model: gpt-6-luna through the Portkey gateway, with PORTKEY_API_KEY from the course-root .env
- one MCP toolset (the campus-customs server), filtered to the tools its role allows
- one delegation tool per other agent, so any agent can ask any other agent for help
- a live event logger that writes every tool call and result to the activity log
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterable

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.messages import FunctionToolCallEvent, FunctionToolResultEvent
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import AbstractToolset, FilteredToolset

from backend.models import AgentName, AgentReply, DelegationRefusal, SPECIALIST_NAMES
from mcp_server import shop

if TYPE_CHECKING:
    from backend.agents.team import AgentTeam

ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
MODEL_NAME = "gpt-6-luna"  # the only model used by any agent
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MAX_DEPTH = 5  # longest chain of agents working one ticket, Boss included
MAX_VISITS_PER_AGENT = 2  # one agent may appear at most twice in a chain, which stops loops
REQUEST_LIMIT = 15  # model calls allowed per agent run


def load_course_env() -> Path | None:
    """Load the first .env found walking up from the project (the shared course-root .env)."""
    for folder in [ROOT, *ROOT.parents]:
        candidate = folder / ".env"
        if candidate.exists():
            load_dotenv(candidate, override=False)
            return candidate
    return None


load_course_env()


@dataclass(frozen=True)
class AgentSpec:
    """Who an agent is: its name, its prompt file, and the only MCP tools it may call."""

    name: AgentName
    title: str
    prompt_file: str
    tools: tuple[str, ...]


@dataclass
class TeamDeps:
    """Per-run context: the ticket being worked and the chain of agents that led to this run."""

    ticket_id: int
    chain: list[AgentName]
    team: AgentTeam


def make_model() -> OpenAIChatModel:
    api_key = os.environ.get("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Add it to the course-root .env file.")
    client = AsyncOpenAI(
        api_key="portkey",
        base_url=os.environ.get("PORTKEY_BASE_URL", PORTKEY_BASE_URL),
        default_headers={"x-portkey-api-key": api_key},
    )
    return OpenAIChatModel(
        MODEL_NAME,
        provider=OpenAIProvider(openai_client=client),
        # The gateway accepts function tools on gpt-6-luna only with reasoning_effort="none".
        settings=OpenAIChatModelSettings(openai_reasoning_effort="none"),
    )


def load_prompt(file_name: str) -> str:
    return (PROMPT_DIR / file_name).read_text()


def check_delegation(chain: list[AgentName], target: AgentName) -> str | None:
    """Return a reason to refuse the delegation, or None if it may proceed."""
    if len(chain) >= MAX_DEPTH:
        return f"delegation depth limit of {MAX_DEPTH} reached; answer with what you already have"
    if chain.count(target) >= MAX_VISITS_PER_AGENT:
        return f"{target} already worked this ticket {MAX_VISITS_PER_AGENT} times in this chain"
    return None


def _delegation_tool(caller: AgentName, target: AgentName, title: str) -> Tool[TeamDeps]:
    async def ask(ctx: RunContext[TeamDeps], question: str) -> AgentReply | DelegationRefusal:
        deps = ctx.deps
        refusal = check_delegation(deps.chain, target)
        if refusal:
            shop.log_event(caller, deps.ticket_id, "delegation_refused", f"-> {target}: {refusal}")
            return DelegationRefusal(target=target, reason=refusal)
        shop.log_event(caller, deps.ticket_id, "delegate", f"-> {target}: {question}")
        return await deps.team.run_agent(target, question, deps.ticket_id, [*deps.chain, target])

    return Tool(
        ask,
        name=f"ask_{target}",
        description=(
            f"Ask the {title} agent ({target}) to do part of this ticket. Give the ticket id and a specific question or "
            "task. You get back its AgentReply: its answer, the actions it took, and any approval or draft ids it created."
        ),
    )


def make_event_logger(agent: AgentName, ticket_id: int):
    """Write each tool call and result to the activity log as it happens, so the board shows live progress."""

    async def log_events(_ctx: RunContext[TeamDeps], events: AsyncIterable[Any]) -> None:
        async for event in events:
            if isinstance(event, FunctionToolCallEvent):
                shop.log_event(agent, ticket_id, "tool_call", f"{event.part.tool_name} {event.part.args}"[:500])
            elif isinstance(event, FunctionToolResultEvent):
                content = getattr(event.result, "content", event.result)
                shop.log_event(agent, ticket_id, "tool_result", str(content)[:500])

    return log_events


def build_agent(spec: AgentSpec, mcp_toolset: AbstractToolset[Any], all_titles: dict[AgentName, str]) -> Agent[TeamDeps, AgentReply]:
    """Build one agent: its prompt, its filtered tools, and a delegation tool for every other agent."""
    allowed = set(spec.tools)
    delegates = [
        _delegation_tool(spec.name, target, all_titles[target])
        for target in ("boss", *SPECIALIST_NAMES)
        if target != spec.name
    ]
    return Agent(
        make_model(),
        name=spec.name,
        deps_type=TeamDeps,
        output_type=AgentReply,
        system_prompt=load_prompt(spec.prompt_file),
        tools=delegates,
        toolsets=[FilteredToolset(mcp_toolset, lambda _ctx, tool_def: tool_def.name in allowed)],
        retries=2,
    )
