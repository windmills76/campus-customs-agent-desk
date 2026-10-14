// Shapes returned by the FastAPI routes in backend/main.py.

export type TicketState = "open" | "blocked" | "resolved";

export interface TicketSummary {
  id: number;
  type: string;
  requester: string;
  subject: string;
  status: string;
  state: TicketState;
  overdue: boolean;
  pending_approvals: number;
}

export interface Approval {
  id: number;
  kind: "invoice_payment" | "rent_payment" | "purchase_order" | "discount" | "question" | string;
  ticket_id: number | null;
  ref_id: number | null;
  amount: number;
  summary: string;
  status: "pending" | "approved" | "rejected";
  requested_by: string;
  requested_at: string;
  result: string | null;
  payload: Record<string, unknown>;
  ticket_subject?: string;
}

export interface OutboxDraft {
  id: number;
  ticket_id: number;
  ticket_subject: string;
  channel: string;
  recipient: string;
  body: string;
  status: string;
  created_by: string;
  created_at: string;
}

export interface ActivityEvent {
  id: number;
  ts: string;
  agent: string;
  ticket_id: number | null;
  event: string;
  detail: string;
}

export interface TicketDetail extends TicketSummary {
  notes: string | null;
  resolution: string | null;
  sku: string | null;
  size: string | null;
  qty: number | null;
  invoice: { id: number; amount: number; due_date: string; overdue: boolean; vendor_name: string } | null;
  lease: { id: number; space_name: string; monthly_rent: number; next_due: string; overdue: boolean } | null;
  approvals: Approval[];
  drafts: { id: number; recipient: string; body: string; status: string }[];
  purchase_orders: { id: number; sku: string; size: string; qty: number; eta: string; status: string }[];
}

export interface CashBalance {
  account: string;
  balance: number;
  date: string;
  pending_payments: number;
  available_after_pending: number;
}

export interface Health {
  ok: boolean;
  working_db: string;
  model: string;
  busy: boolean;
  current_ticket: number | null;
  queue: number[];
}
