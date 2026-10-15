import { useState } from "react";
import type { ActivityEvent, TicketDetail, TicketSummary } from "../types";
import { AGENTS, AGENT_KEYS, agentViews, currentRun, isAgentKey, runSummary } from "../agents";
import type { AgentKey, AgentView } from "../agents";
import { agentLabel, money, stateLabel, statusLabel, timeOf, typeLabel } from "../format";

interface TicketPanelProps {
  summary: TicketSummary | undefined;
  detail: TicketDetail | null;
  events: ActivityEvent[];
  busy: boolean;
  runningHere: boolean;
  onStart: (id: number) => void;
  onNote: (id: number, note: string) => Promise<void>;
  onConfirm: (id: number, acceptedQty: number) => Promise<void>;
  startError: string | null;
}

export function TicketPanel({ summary, detail, events, busy, runningHere, onStart, onNote, onConfirm, startError }: TicketPanelProps) {
  if (!summary) {
    return (
      <section className="column main-column" aria-label="Ticket">
        <div className="empty-state">
          <div className="empty-title">Pick a ticket</div>
          <p>Choose a ticket on the board to see the team's work on it, or start the team on it.</p>
        </div>
      </section>
    );
  }

  const run = currentRun(events);
  const views = agentViews(run, runningHere);
  const summaries = runSummary(run);
  const finished = !runningHere && run.length > 0;
  const resolved = summary.state === "resolved";
  const canStart = !busy && !resolved;

  return (
    <section className="column main-column" aria-label="Ticket detail">
      <header className="ticket-hero">
        <div>
          <div className="hero-kicker">
            Ticket #{summary.id} · {typeLabel(summary.type)}
          </div>
          <h1>{summary.subject}</h1>
          <div className="hero-meta">
            {summary.requester}
            {detail?.sku && <> · {detail.sku}{detail.size ? ` ${detail.size}` : ""}{detail.qty ? ` × ${detail.qty}` : ""}</>}
          </div>
          <div className="hero-tags">
            <span className={`state-pill ${summary.state}`}>{stateLabel(summary.state)}</span>
            <span className={`agent-pill ${summary.agent_outcome}`}>{agentLabel(summary.agent_outcome)}</span>
            {statusLabel(summary.status) !== stateLabel(summary.state) && (
              <span className="status-tag">{statusLabel(summary.status)}</span>
            )}
            {summary.overdue && <span className="overdue">Overdue</span>}
          </div>
        </div>
        <div className="hero-action">
          <button
            className="primary-button large"
            onClick={() => onStart(summary.id)}
            disabled={!canStart}
            title={resolved ? "This ticket is already resolved" : busy ? "The team is busy with another ticket" : ""}
          >
            {runningHere ? "Team working…" : resolved ? "Resolved" : finished ? "Run again" : "Start agent team"}
          </button>
          {startError && <div className="inline-error">{startError}</div>}
        </div>
      </header>

      {detail?.resolution && (
        <div className={`resolution-banner ${summary.state}`} role="note">
          <div className="resolution-title">{resolved ? "Resolved" : summary.state === "blocked" ? "Blocked" : "Team decision"}</div>
          <div>{detail.resolution}</div>
        </div>
      )}

      <div className="section-head">
        <h2>The team</h2>
        <span className="muted">{runningHere ? "Working on this ticket now" : finished ? "Last run" : "Waiting to start"}</span>
      </div>
      <div className="agent-grid">
        {AGENT_KEYS.map((key) => (
          <AgentCard key={key} agentKey={key} view={views[key]} />
        ))}
      </div>

      {detail?.sku && <StockCard detail={detail} onConfirm={onConfirm} disabled={runningHere} />}

      <NoteBox ticketId={summary.id} onNote={onNote} disabled={runningHere} />

      <div className="two-up">
        <div className="card">
          <div className="section-head">
            <h2>Live activity</h2>
            {runningHere && <span className="live-badge">Live</span>}
          </div>
          <Timeline events={run} />
        </div>

        <div className="card">
          <div className="section-head">
            <h2>What each agent did</h2>
          </div>
          {summaries.length === 0 ? (
            <p className="muted">Nothing yet. Start the team to see each agent's work.</p>
          ) : (
            <ul className="summary-list">
              {summaries.map((item) => (
                <li key={item.key}>
                  <div className="summary-head">
                    <span className="avatar small" style={{ background: AGENTS[item.key].color }}>
                      {AGENTS[item.key].initial}
                    </span>
                    <strong>{AGENTS[item.key].name}</strong>
                    <span className="muted">{item.calls} tool {item.calls === 1 ? "call" : "calls"}</span>
                  </div>
                  {item.tools.length > 0 && (
                    <div className="chips">
                      {item.tools.map((tool) => (
                        <code key={tool} className="chip">{tool}</code>
                      ))}
                    </div>
                  )}
                  {item.said && <p className="summary-said">{item.said}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {detail && detail.approvals.length > 0 && (
        <div className="card">
          <div className="section-head">
            <h2>Requests on this ticket</h2>
          </div>
          <ul className="request-list">
            {detail.approvals.map((a) => (
              <li key={a.id}>
                <span className={`status-dot ${a.status}`} aria-hidden />
                <span>{a.summary}</span>
                <span className="muted">{a.status}</span>
                {a.amount > 0 && <span className="amount">{money(a.amount)}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function StockCard({
  detail,
  onConfirm,
  disabled,
}: {
  detail: TicketDetail;
  onConfirm: (id: number, acceptedQty: number) => Promise<void>;
  disabled: boolean;
}) {
  const requested = detail.qty ?? 0;
  const [accepted, setAccepted] = useState(requested);
  const [saving, setSaving] = useState(false);
  const missing = detail.missing_units ?? 0;
  return (
    <div className="card stock-card">
      <div className="section-head">
        <h2>Stock for {detail.sku} {detail.size}</h2>
        <span className="muted">Requested {requested}</span>
      </div>
      <div className="stock-grid">
        <div><b>On hand</b><span>{detail.on_hand ?? 0}</span></div>
        <div><b>Incoming</b><span>{detail.incoming_units ?? 0}</span></div>
        <div className={missing > 0 ? "short" : ""}><b>Missing</b><span>{missing}</span></div>
      </div>
      {(detail.incoming ?? []).length > 0 && (
        <p className="muted">
          {(detail.incoming ?? []).map((p) => `PO #${p.id}: ${p.qty} unit(s), arriving ${p.eta}`).join(" · ")}
        </p>
      )}
      <form
        className="answer-form"
        onSubmit={async (event) => {
          event.preventDefault();
          setSaving(true);
          await onConfirm(detail.id, accepted);
          setSaving(false);
        }}
      >
        <label className="muted" htmlFor="accepted">Customer accepts</label>
        <input
          id="accepted"
          type="number"
          min={1}
          max={requested}
          value={accepted}
          onChange={(event) => setAccepted(Number(event.target.value))}
          disabled={saving || disabled}
        />
        <button className="primary-button" type="submit" disabled={saving || disabled || accepted < 1 || accepted > requested}>
          {saving ? "Saving…" : "Record customer confirmation"}
        </button>
      </form>
    </div>
  );
}

function NoteBox({ ticketId, onNote, disabled }: { ticketId: number; onNote: (id: number, note: string) => Promise<void>; disabled: boolean }) {
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  return (
    <form
      className="card note-box"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!text.trim()) return;
        setSaving(true);
        await onNote(ticketId, text.trim());
        setSaving(false);
        setText("");
      }}
    >
      <div className="section-head">
        <h2>Add a note for the team</h2>
        <span className="muted">Boss reads it on the next run</span>
      </div>
      <div className="answer-form">
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="For example: target unit price is $29.33 per hoodie"
          aria-label="Note for the team"
          disabled={saving || disabled}
        />
        <button className="primary-button" type="submit" disabled={saving || disabled || !text.trim()}>
          {saving ? "Saving…" : "Add note"}
        </button>
      </div>
    </form>
  );
}

function AgentCard({ agentKey, view }: { agentKey: AgentKey; view: AgentView }) {
  const agent = AGENTS[agentKey];
  const line = view.status === "working" ? view.doing : view.said;
  return (
    <article className={`agent-card ${view.status}`} style={{ ["--agent" as string]: agent.color }}>
      <div className="agent-head">
        <span className="avatar" style={{ background: agent.color }}>{agent.initial}</span>
        <div className="agent-names">
          <div className="agent-name">{agent.name}</div>
          <div className="agent-role">{agent.role}</div>
        </div>
        <span className={`agent-status ${view.status}`}>
          {view.status === "working" ? "Working" : view.status === "done" ? "Done" : "Idle"}
        </span>
      </div>
      <div className="bubble">
        {line ? <p>{line}</p> : <p className="muted">{view.status === "idle" ? "Not on this ticket yet." : "…"}</p>}
      </div>
      {view.tools.length > 0 && (
        <div className="chips">
          {view.tools.slice(0, 4).map((tool) => (
            <code key={tool} className="chip">{tool}</code>
          ))}
          {view.tools.length > 4 && <span className="chip muted">+{view.tools.length - 4}</span>}
        </div>
      )}
    </article>
  );
}

function Timeline({ events }: { events: ActivityEvent[] }) {
  if (events.length === 0) {
    return <p className="muted">No activity for this run yet.</p>;
  }
  return (
    <ol className="timeline">
      {events.map((event) => (
        <TimelineItem key={event.id} event={event} />
      ))}
    </ol>
  );
}

function TimelineItem({ event }: { event: ActivityEvent }) {
  const agent = isAgentKey(event.agent) ? AGENTS[event.agent] : null;
  const who = agent ? agent.name : event.agent === "system" ? "System" : "Human";
  const color = agent?.color ?? "#6e7787";
  const time = timeOf(event.ts);

  if (event.event === "status") {
    return <li className="timeline-divider"><span>{event.detail}</span></li>;
  }
  if (event.event === "message") {
    return (
      <li className="timeline-row">
        <span className="timeline-dot" style={{ background: color }} />
        <div className="bubble inline">
          <div className="timeline-who">{who} <span className="muted">{time}</span></div>
          <p>{event.detail}</p>
        </div>
      </li>
    );
  }
  if (event.event === "tool_call") {
    return (
      <li className="timeline-row tool">
        <span className="timeline-dot" style={{ background: color }} />
        <div>
          <span className="muted">{who} · {time}</span>
          <code className="tool-call">{event.detail}</code>
        </div>
      </li>
    );
  }
  if (event.event === "tool_result") {
    return (
      <li className="timeline-row result">
        <span className="timeline-dot tiny" />
        <details>
          <summary>Result</summary>
          <code className="tool-result">{event.detail}</code>
        </details>
      </li>
    );
  }
  if (event.event === "decision") {
    return (
      <li className="timeline-row decision">
        <span className="timeline-dot" style={{ background: color }} />
        <div className="decision-card">
          <div className="timeline-who">Final call · {time}</div>
          <p>{event.detail}</p>
        </div>
      </li>
    );
  }
  const tone = event.event.includes("error") || event.event.includes("refused") ? "warn" : "info";
  const label = event.event.replace(/_/g, " ");
  return (
    <li className="timeline-row">
      <span className="timeline-dot" style={{ background: tone === "warn" ? "#c2410c" : color }} />
      <div className={`event-note ${tone}`}>
        <span className="event-label">{label}</span>
        <span>{event.detail}</span>
        <span className="muted">{who} · {time}</span>
      </div>
    </li>
  );
}
