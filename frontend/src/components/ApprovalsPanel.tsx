import { useState } from "react";
import type { Approval } from "../types";
import { kindLabel, money, timeOf } from "../format";

interface ApprovalsPanelProps {
  approvals: Approval[];
  selectedTicketId: number | null;
  onApprove: (approval: Approval) => Promise<void>;
  onReject: (approval: Approval) => Promise<void>;
  onAnswer: (approval: Approval, answer: string) => Promise<void>;
}

const MONEY_KINDS = new Set(["invoice_payment", "rent_payment", "purchase_order"]);

export function ApprovalsPanel({ approvals, selectedTicketId, onApprove, onReject, onAnswer }: ApprovalsPanelProps) {
  // Requests for the open ticket come first, then everything else on the board.
  const ordered = [...approvals].sort((a, b) => {
    const aHere = a.ticket_id === selectedTicketId ? 0 : 1;
    const bHere = b.ticket_id === selectedTicketId ? 0 : 1;
    return aHere - bHere || a.id - b.id;
  });

  return (
    <section className="column approvals-column" aria-label="Approvals">
      <div className="column-head">
        <h2>Waiting for you</h2>
        <span className="count">{approvals.length}</span>
      </div>
      {ordered.length === 0 ? (
        <div className="empty-state small">
          <div className="empty-title">All clear</div>
          <p>Nothing needs your approval right now.</p>
        </div>
      ) : (
        <ul className="approval-list">
          {ordered.map((approval) => (
            <ApprovalCard
              key={approval.id}
              approval={approval}
              here={approval.ticket_id === selectedTicketId}
              onApprove={onApprove}
              onReject={onReject}
              onAnswer={onAnswer}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function ApprovalCard({
  approval,
  here,
  onApprove,
  onReject,
  onAnswer,
}: {
  approval: Approval;
  here: boolean;
  onApprove: (approval: Approval) => Promise<void>;
  onReject: (approval: Approval) => Promise<void>;
  onAnswer: (approval: Approval, answer: string) => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  const [answer, setAnswer] = useState("");
  const [working, setWorking] = useState(false);
  const isQuestion = approval.kind === "question";
  const isMoney = MONEY_KINDS.has(approval.kind);

  const run = async (fn: () => Promise<void>) => {
    setWorking(true);
    try {
      await fn();
    } finally {
      setWorking(false);
      setConfirming(false);
    }
  };

  return (
    <li className={`approval-card ${here ? "here" : ""} ${isQuestion ? "question" : ""}`}>
      <div className="approval-top">
        <span className="kind">{kindLabel(approval.kind)}</span>
        <span className="muted">#{approval.id} · {timeOf(approval.requested_at)}</span>
      </div>
      {isMoney && approval.amount > 0 && <div className="approval-amount">{money(approval.amount)}</div>}
      <p className="approval-summary">{approval.summary}</p>
      <div className="approval-ticket">
        {approval.ticket_id !== null ? `Ticket #${approval.ticket_id}` : "No ticket"} · requested by {approval.requested_by}
      </div>

      {isQuestion ? (
        <form
          className="answer-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (answer.trim()) run(() => onAnswer(approval, answer.trim()).then(() => setAnswer("")));
          }}
        >
          <input
            value={answer}
            onChange={(event) => setAnswer(event.target.value)}
            placeholder="Type your answer for Boss"
            aria-label="Answer for Boss"
            disabled={working}
          />
          <button className="primary-button" type="submit" disabled={working || !answer.trim()}>
            Send answer
          </button>
        </form>
      ) : confirming ? (
        <div className="confirm-row">
          <span>{isMoney ? `Confirm ${money(approval.amount)} out of checking?` : "Confirm this decision?"}</span>
          <button className="ghost-button" onClick={() => setConfirming(false)} disabled={working}>Back</button>
          <button className="primary-button" onClick={() => run(() => onApprove(approval))} disabled={working}>
            {working ? "Approving…" : "Yes, approve"}
          </button>
        </div>
      ) : (
        <div className="approval-actions">
          <button className="primary-button" onClick={() => setConfirming(true)} disabled={working}>
            Approve
          </button>
          <button className="ghost-button" onClick={() => run(() => onReject(approval))} disabled={working}>
            Decline
          </button>
        </div>
      )}
    </li>
  );
}
