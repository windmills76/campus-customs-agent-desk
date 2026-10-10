"""Facilities: handles the shop space side: leases, rent due dates, and rent payment requests for human approval."""

from .base import AgentSpec

SPEC = AgentSpec(
    name="facilities",
    title="Facilities",
    prompt_file="facilities.md",
    tools=(
        "get_desk",
        "get_ticket",
        "list_leases",
        "get_lease_rent_status",
        "get_cash",
        "request_rent_payment",
        "add_ticket_note",
    ),
)
