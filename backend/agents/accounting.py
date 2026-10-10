"""Accounting: watches cash and invoices, checks margins, and prepares payments, purchase orders, and discounts for human approval.

Accounting never pays or orders anything itself. Every request it makes waits for a person.
"""

from .base import AgentSpec

SPEC = AgentSpec(
    name="accounting",
    title="Accounting",
    prompt_file="accounting.md",
    tools=(
        "get_desk",
        "get_ticket",
        "get_cash",
        "list_invoices",
        "list_open_vendor_invoices",
        "list_payments",
        "overdue_report",
        "margin_check",
        "get_pricing",
        "list_vendors",
        "list_approvals",
        "request_invoice_payment",
        "request_purchase_order",
        "request_discount_approval",
        "add_ticket_note",
    ),
)
