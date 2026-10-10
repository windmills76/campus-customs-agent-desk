import { useEffect, useRef, useState } from "react";
import type { CashBalance } from "../types";
import { money } from "../format";

interface HeaderProps {
  online: boolean;
  busy: boolean;
  runningLabel: string | null;
  cash: CashBalance | null;
  onReset: () => void;
}

/** The balance eases to its new value, and a chip shows how much went out. */
function useAnimatedBalance(target: number | undefined) {
  const [shown, setShown] = useState(target ?? 0);
  const shownRef = useRef(shown);
  const hasShown = useRef(false);
  useEffect(() => {
    if (target === undefined || target === shownRef.current) return;
    if (!hasShown.current) {
      // First value on page load: show it straight away instead of counting up from zero.
      hasShown.current = true;
      shownRef.current = target;
      setShown(target);
      return;
    }
    const from = shownRef.current;
    const started = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const progress = Math.min(1, (now - started) / 900);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = from + (target - from) * eased;
      shownRef.current = value;
      setShown(value);
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target]);
  return shown;
}

export function Header({ online, busy, runningLabel, cash, onReset }: HeaderProps) {
  const balance = useAnimatedBalance(cash?.balance);
  const [delta, setDelta] = useState<number | null>(null);
  const lastBalance = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (cash === null) return;
    if (lastBalance.current !== undefined && cash.balance !== lastBalance.current) {
      setDelta(cash.balance - lastBalance.current);
      const timer = window.setTimeout(() => setDelta(null), 4000);
      lastBalance.current = cash.balance;
      return () => window.clearTimeout(timer);
    }
    lastBalance.current = cash.balance;
  }, [cash]);

  const teamLabel = !online ? "Backend offline" : busy ? (runningLabel ?? "Team working") : "Team idle";

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark" aria-hidden>CC</div>
        <div>
          <div className="brand-name">Campus Customs</div>
          <div className="brand-sub">Agent desk</div>
        </div>
      </div>

      <div className={`team-status ${!online ? "offline" : busy ? "busy" : "idle"}`} role="status">
        <span className="pulse-dot" aria-hidden />
        {teamLabel}
      </div>

      <div className="topbar-right">
        <div className="cash-card" aria-label="Checking balance">
          <div className="cash-label">Checking</div>
          <div className="cash-value">{cash ? money(balance) : "—"}</div>
          {cash && (
            <div className="cash-sub">
              {money(cash.available_after_pending)} available
              {cash.pending_payments > 0 && <span> · {money(cash.pending_payments)} awaiting approval</span>}
            </div>
          )}
          {delta !== null && delta < 0 && <div className="cash-delta">−{money(Math.abs(delta))}</div>}
        </div>
        <button className="ghost-button" onClick={onReset} disabled={busy}>
          Reset database
        </button>
      </div>
    </header>
  );
}
