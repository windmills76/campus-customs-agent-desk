"""Boss: reads each ticket, decides which specialist(s) should act, and makes the final call.

Boss has read-only tools plus add_ticket_note. It cannot request money, stock, or discounts itself.
Its final output is a BossDecision, which the team writes to the ticket.
"""

from .base import AgentSpec

SPEC = AgentSpec(
    name="boss",
    title="Boss",
    prompt_file="boss.md",
    tools=(
        "get_desk",
        "list_tickets",
        "get_ticket",
        "overdue_report",
        "list_approvals",
        "add_ticket_note",
        "ask_human",
    ),
)
