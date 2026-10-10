"""Customer service: drafts messages to customers. Drafts stay on the board. Nothing is ever sent."""

from .base import AgentSpec

SPEC = AgentSpec(
    name="customer_service",
    title="Customer Service",
    prompt_file="customer_service.md",
    tools=(
        "get_desk",
        "get_ticket",
        "check_inventory_stock",
        "restock_options",
        "create_draft",
        "add_ticket_note",
    ),
)
