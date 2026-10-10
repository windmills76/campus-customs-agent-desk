import type { ActivityEvent } from "./types";

export const AGENT_KEYS = ["boss", "inventory", "accounting", "facilities", "customer_service"] as const;
export type AgentKey = (typeof AGENT_KEYS)[number];

export const AGENTS: Record<AgentKey, { name: string; role: string; color: string; initial: string }> = {
  boss: { name: "Boss", role: "Reads the ticket, routes it, makes the call", color: "#1d3b78", initial: "B" },
  inventory: { name: "Inventory", role: "Stock, shortfalls, restock vendors", color: "#0a84ff", initial: "I" },
  accounting: { name: "Accounting", role: "Cash, invoices, margins, requests", color: "#00a3c4", initial: "A" },
  facilities: { name: "Facilities", role: "Leases and rent", color: "#5e5ce6", initial: "F" },
  customer_service: { name: "Customer Service", role: "Drafts customer messages", color: "#4cc9f0", initial: "C" },
};

export const isAgentKey = (value: string): value is AgentKey => (AGENT_KEYS as readonly string[]).includes(value);

/** The events from the most recent run: everything after the last "status -> in_progress" event. */
export function currentRun(events: ActivityEvent[]): ActivityEvent[] {
  let start = 0;
  events.forEach((event, index) => {
    if (event.event === "status" && event.detail.includes("in_progress")) start = index;
  });
  return events.slice(start);
}

export type AgentStatus = "idle" | "working" | "done";

export interface AgentView {
  status: AgentStatus;
  said: string | null; // the agent's latest reply
  doing: string | null; // what it is doing right now
  calls: number;
  tools: string[];
}

const toolName = (detail: string) => detail.split(" ")[0];

/** Work out each agent's status from the run's events. Activity after the agent's last reply means it is still working. */
export function agentViews(run: ActivityEvent[], running: boolean): Record<AgentKey, AgentView> {
  const views = {} as Record<AgentKey, AgentView>;
  for (const key of AGENT_KEYS) {
    views[key] = { status: "idle", said: null, doing: null, calls: 0, tools: [] };
  }
  const lastActivity: Partial<Record<AgentKey, number>> = {};
  const lastReply: Partial<Record<AgentKey, number>> = {};

  run.forEach((event, index) => {
    if (!isAgentKey(event.agent)) return;
    const view = views[event.agent];
    if (event.event === "tool_call") {
      view.calls += 1;
      const tool = toolName(event.detail);
      if (!view.tools.includes(tool)) view.tools.push(tool);
      view.doing = `Using ${tool}`;
      lastActivity[event.agent] = index;
    } else if (event.event === "delegate") {
      view.doing = `Asking ${event.detail.split("->")[1]?.split(":")[0]?.trim() ?? "a colleague"}`;
      lastActivity[event.agent] = index;
    } else if (event.event === "message" && !event.detail.startsWith("assigned:")) {
      view.said = event.detail;
      lastReply[event.agent] = index;
    } else if (event.event === "decision") {
      view.said = event.detail;
      lastReply[event.agent] = index;
    }
  });

  for (const key of AGENT_KEYS) {
    const view = views[key];
    const acted = lastActivity[key] ?? -1;
    const replied = lastReply[key] ?? -1;
    const touched = acted >= 0 || replied >= 0;
    if (!touched) {
      // Boss starts a run by reading the ticket, so show it working before its first event arrives.
      view.status = running && key === "boss" ? "working" : "idle";
      view.doing = view.status === "working" ? "Reading the ticket" : null;
    } else if (running && acted > replied) {
      view.status = "working";
    } else {
      view.status = "done";
      view.doing = null;
    }
  }
  return views;
}

export interface AgentSummary {
  key: AgentKey;
  calls: number;
  tools: string[];
  said: string | null;
}

/** What each agent did on this ticket in the current run, for the summary card. */
export function runSummary(run: ActivityEvent[]): AgentSummary[] {
  const views = agentViews(run, false);
  return AGENT_KEYS.map((key) => ({ key, calls: views[key].calls, tools: views[key].tools, said: views[key].said }))
    .filter((item) => item.calls > 0 || item.said);
}
