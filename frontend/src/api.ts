import type { ActivityEvent, Approval, CashBalance, Health, OutboxDraft, TicketDetail, TicketSummary } from "./types";

// The backend runs on port 8000. Set VITE_API_URL in frontend/.env to point somewhere else.
export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(0, `Cannot reach the backend at ${API_URL}. Is it running on port 8000?`);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = typeof body.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  tickets: () => request<TicketSummary[]>("/api/tickets"),
  ticket: (id: number) => request<TicketDetail>(`/api/tickets/${id}`),
  runTicket: (id: number) => request<{ ticket_id: number; started: boolean }>(`/api/tickets/${id}/run`, { method: "POST" }),
  events: (ticketId: number) => request<ActivityEvent[]>(`/api/events?ticket_id=${ticketId}&limit=500`),
  pendingApprovals: () => request<Approval[]>("/api/approvals?status=pending"),
  approve: (id: number) => request(`/api/approvals/${id}/approve`, { method: "POST" }),
  reject: (id: number, reason: string) =>
    request(`/api/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  answer: (id: number, answer: string) =>
    request(`/api/approvals/${id}/answer`, { method: "POST", body: JSON.stringify({ answer }) }),
  outbox: () => request<OutboxDraft[]>("/api/outbox"),
  draftReady: (id: number) => request(`/api/outbox/${id}/ready`, { method: "POST" }),
  draftDiscard: (id: number) => request(`/api/outbox/${id}/discard`, { method: "POST" }),
  addNote: (ticketId: number, note: string) =>
    request(`/api/tickets/${ticketId}/notes`, { method: "POST", body: JSON.stringify({ note }) }),
  cash: () => request<CashBalance>("/api/cash/balance"),
  reset: () => request<{ ok: boolean }>("/api/reset", { method: "POST" }),
};
