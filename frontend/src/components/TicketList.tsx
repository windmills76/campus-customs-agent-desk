import type { TicketSummary } from "../types";
import { stateLabel, statusLabel, typeLabel } from "../format";

interface TicketListProps {
  tickets: TicketSummary[];
  selectedId: number | null;
  runningId: number | null;
  onSelect: (id: number) => void;
}

export function TicketList({ tickets, selectedId, runningId, onSelect }: TicketListProps) {
  return (
    <section className="column" aria-label="Tickets">
      <div className="column-head">
        <h2>Board</h2>
        <span className="count">{tickets.length} tickets</span>
      </div>
      <ul className="ticket-list">
        {tickets.map((ticket) => {
          const selected = ticket.id === selectedId;
          const running = ticket.id === runningId;
          return (
            <li key={ticket.id}>
              <button
                className={`ticket-card ${selected ? "selected" : ""} ${ticket.state}`}
                onClick={() => onSelect(ticket.id)}
                aria-pressed={selected}
              >
                <div className="ticket-top">
                  <span className="ticket-id">#{ticket.id}</span>
                  <span className={`state-pill ${ticket.state}`}>{stateLabel(ticket.state)}</span>
                </div>
                <div className="ticket-subject">{ticket.subject}</div>
                <div className="ticket-meta">
                  {typeLabel(ticket.type)} · {ticket.requester}
                </div>
                <div className="ticket-foot">
                  <span className={`status-text ${running ? "running" : ""}`}>
                    {running ? "Team working…" : statusLabel(ticket.status)}
                  </span>
                  {ticket.overdue && <span className="overdue">Overdue</span>}
                  {ticket.pending_approvals > 0 && (
                    <span className="approval-count">{ticket.pending_approvals} to approve</span>
                  )}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
