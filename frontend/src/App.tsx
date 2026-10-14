import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { ActivityEvent, Approval, CashBalance, OutboxDraft, TicketDetail, TicketSummary } from "./types";
import { Header } from "./components/Header";
import { TicketList } from "./components/TicketList";
import { TicketPanel } from "./components/TicketPanel";
import { ApprovalsPanel } from "./components/ApprovalsPanel";
import { money, statusLabel } from "./format";

interface Toast {
  id: number;
  message: string;
  tone: "info" | "success" | "error";
}

const message = (error: unknown) => (error instanceof ApiError || error instanceof Error ? error.message : "Something went wrong");

export function App() {
  const [online, setOnline] = useState(true);
  const [busy, setBusy] = useState(false);
  const [queue, setQueue] = useState<number[]>([]);
  const [tickets, setTickets] = useState<TicketSummary[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [outbox, setOutbox] = useState<OutboxDraft[]>([]);
  const [cash, setCash] = useState<CashBalance | null>(null);
  // ?ticket=101 opens the desk with that ticket already selected (handy for links and screenshots).
  const initialTicket = (() => {
    const value = Number(new URLSearchParams(window.location.search).get("ticket"));
    return Number.isInteger(value) && value > 0 ? value : null;
  })();
  const [selectedId, setSelectedId] = useState<number | null>(initialTicket);
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [runningId, setRunningId] = useState<number | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);

  // Refs let the polling loop read the latest values without restarting.
  const selectedRef = useRef<number | null>(initialTicket);
  const busyRef = useRef(false);
  const runningRef = useRef<number | null>(null);

  const notify = useCallback((text: string, tone: Toast["tone"] = "info") => {
    setToast({ id: Date.now(), message: text, tone });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const loadSelected = useCallback(async (id: number) => {
    try {
      const [ticketDetail, ticketEvents] = await Promise.all([api.ticket(id), api.events(id)]);
      if (selectedRef.current === id) {
        setDetail(ticketDetail);
        setEvents(ticketEvents);
      }
    } catch {
      // The next poll retries; the header already shows if the backend is offline.
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [health, board, pending, balance, drafts] = await Promise.all([
        api.health(),
        api.tickets(),
        api.pendingApprovals(),
        api.cash(),
        api.outbox(),
      ]);
      setOutbox(drafts);
      setOnline(true);
      setBusy(health.busy);
      setQueue(health.queue);
      busyRef.current = health.busy;
      setTickets(board);
      setApprovals(pending);
      setCash(balance);

      const started = runningRef.current;
      if (started !== null && !health.busy) {
        const finished = board.find((ticket) => ticket.id === started);
        runningRef.current = null;
        setRunningId(null);
        if (finished) {
          notify(
            `Run finished: ticket #${finished.id} is ${finished.state === "resolved" ? "resolved" : statusLabel(finished.status).toLowerCase()}.`,
            "success",
          );
        }
      }
    } catch (error) {
      setOnline(false);
      if (error instanceof ApiError && error.status === 0) return;
    }
  }, [notify]);

  // One loop keeps the board, approvals, cash, and the open ticket fresh.
  useEffect(() => {
    let cancelled = false;
    let timer = 0;
    const tick = async () => {
      await refresh();
      const id = selectedRef.current;
      if (id !== null) await loadSelected(id);
      if (!cancelled) timer = window.setTimeout(tick, busyRef.current ? 1200 : 2500);
    };
    tick();
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [refresh, loadSelected]);

  const selectTicket = (id: number) => {
    selectedRef.current = id;
    setSelectedId(id);
    setDetail(null);
    setEvents([]);
    setStartError(null);
    loadSelected(id);
  };

  const startTeam = async (id: number) => {
    setStartError(null);
    try {
      await api.runTicket(id);
      runningRef.current = id;
      busyRef.current = true;
      setRunningId(id);
      setBusy(true);
      notify(`Agent team started on ticket #${id}.`);
    } catch (error) {
      setStartError(message(error));
    }
  };

  const markReady = async (draft: OutboxDraft) => {
    try {
      await api.draftReady(draft.id);
      notify(`Draft #${draft.id} marked ready. Nothing was sent; send it yourself.`, "success");
    } catch (error) {
      notify(message(error), "error");
    }
    await refresh();
  };

  const discardDraft = async (draft: OutboxDraft) => {
    try {
      await api.draftDiscard(draft.id);
      notify(`Draft #${draft.id} discarded.`);
    } catch (error) {
      notify(message(error), "error");
    }
    await refresh();
  };

  const addNote = async (ticketId: number, note: string) => {
    try {
      await api.addNote(ticketId, note);
      notify("Note added. Run the team again so it reads your note.", "success");
      await loadSelected(ticketId);
    } catch (error) {
      notify(message(error), "error");
    }
  };

  const approve = async (approval: Approval) => {
    try {
      await api.approve(approval.id);
      notify(
        approval.amount > 0 ? `Approved. ${money(approval.amount)} went out of checking.` : "Approved.",
        "success",
      );
    } catch (error) {
      notify(message(error), "error");
    }
    await refresh();
    if (selectedRef.current !== null) await loadSelected(selectedRef.current);
  };

  const reject = async (approval: Approval) => {
    try {
      await api.reject(approval.id, "Declined on the desk dashboard");
      notify("Declined. The ticket will be picked up again on its next run.");
    } catch (error) {
      notify(message(error), "error");
    }
    await refresh();
  };

  const answer = async (approval: Approval, text: string) => {
    try {
      await api.answer(approval.id, text);
      notify(`Answer sent to Boss for ticket #${approval.ticket_id}.`, "success");
    } catch (error) {
      notify(message(error), "error");
    }
    await refresh();
  };

  const reset = async () => {
    if (!window.confirm("Reset the working database to the original values? All runs and approvals will be cleared.")) return;
    try {
      await api.reset();
      selectedRef.current = null;
      setSelectedId(null);
      setDetail(null);
      setEvents([]);
      notify("Database reset to the original values.", "success");
    } catch (error) {
      notify(message(error), "error");
    }
    await refresh();
  };

  const summary = tickets.find((ticket) => ticket.id === selectedId);
  const runningLabel = [
    runningId !== null ? `Working on #${runningId}` : null,
    queue.length > 0 ? `next: #${queue.join(", #")}` : null,
  ].filter(Boolean).join(" · ") || null;

  return (
    <div className="app">
      <Header online={online} busy={busy} runningLabel={runningLabel} cash={cash} onReset={reset} />

      {!online && (
        <div className="offline-banner" role="alert">
          The backend is not responding at http://localhost:8000. Start it from the backend folder with <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}

      <main className="layout">
        <TicketList tickets={tickets} selectedId={selectedId} runningId={runningId} onSelect={selectTicket} />
        <TicketPanel
          summary={summary}
          detail={detail}
          events={events}
          busy={busy}
          runningHere={runningId !== null && runningId === selectedId}
          onStart={startTeam}
          onNote={addNote}
          startError={startError}
        />
        <ApprovalsPanel
          approvals={approvals}
          selectedTicketId={selectedId}
          onApprove={approve}
          onReject={reject}
          onAnswer={answer}
          outbox={outbox}
          onMarkReady={markReady}
          onDiscard={discardDraft}
        />
      </main>

      {toast && (
        <div className={`toast ${toast.tone}`} role="status" key={toast.id}>
          {toast.message}
        </div>
      )}
    </div>
  );
}
