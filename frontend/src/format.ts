const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export const money = (value: number) => usd.format(value);

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "Team working",
  awaiting_approval: "Awaiting approval",
  waiting_stock: "Waiting on stock",
  resolved: "Resolved",
  blocked: "Blocked",
};

export const stateLabel = (state: string) =>
  state === "resolved" ? "Resolved" : state === "blocked" ? "Blocked" : state === "waiting" ? "Pending inventory" : "Open";

export const agentLabel = (outcome: string) => (outcome === "needs_you" ? "Agent needs you" : "Agent complete");

export const statusLabel = (status: string) => STATUS_LABELS[status] ?? status.replace(/_/g, " ");

const KIND_LABELS: Record<string, string> = {
  invoice_payment: "Pay vendor invoice",
  rent_payment: "Pay rent",
  purchase_order: "Purchase order",
  discount: "Discount",
  question: "Question from Boss",
};

export const kindLabel = (kind: string) => KIND_LABELS[kind] ?? kind.replace(/_/g, " ");

export const TYPE_LABELS: Record<string, string> = {
  customer_order: "Customer order",
  rent_notice: "Rent notice",
  price_override: "Price override",
};

export const typeLabel = (type: string) => TYPE_LABELS[type] ?? type;

export const timeOf = (iso: string) => {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
};
