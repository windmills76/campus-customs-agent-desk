"""Inventory: checks stock by SKU and size, spots shortfalls, finds vendors that can restock, and fills orders from stock."""

from .base import AgentSpec

SPEC = AgentSpec(
    name="inventory",
    title="Inventory",
    prompt_file="inventory.md",
    tools=(
        "get_desk",
        "get_ticket",
        "check_inventory_stock",
        "restock_options",
        "list_vendors",
        "get_pricing",
        "fulfill_order",
        "add_ticket_note",
    ),
)
