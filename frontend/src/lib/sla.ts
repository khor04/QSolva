import { useEffect, useState } from "react";
import type { Ticket } from "./types";

// The backend decides the deadlines (services/sla_policy.py) and sends them on
// every ticket; this only decides which one a ticket is currently waiting on
// and how to say it. Mirrors services/sla.overdue_clause: first response until
// an admin claims/replies, then resolution.
export type SlaPhase = "response" | "resolution" | "awaiting_confirmation" | "closed";
export type SlaLevel = "on_time" | "due_soon" | "overdue";

export interface SlaState {
  phase: SlaPhase;
  // Only set while the ticket is waiting on an admin (response/resolution).
  due: Date | null;
  // Length of the window that ends at `due`, e.g. for "Within 1 day".
  windowMs: number;
  // Negative once overdue.
  msUntilDue: number;
  level: SlaLevel | null;
}

// "Due soon" once less than a quarter of the window is left.
const DUE_SOON_FRACTION = 0.25;

export function getSla(ticket: Ticket, now: number = Date.now()): SlaState {
  if (ticket.status === "closed") {
    return { phase: "closed", due: null, windowMs: 0, msUntilDue: 0, level: null };
  }
  if (ticket.status === "resolved") {
    return { phase: "awaiting_confirmation", due: null, windowMs: 0, msUntilDue: 0, level: null };
  }
  const responded = ticket.first_response_at != null;
  const due = new Date(responded ? ticket.resolution_due_at : ticket.response_due_at);
  const msUntilDue = due.getTime() - now;
  const windowMs = due.getTime() - new Date(ticket.created_at).getTime();
  const level: SlaLevel =
    msUntilDue < 0 ? "overdue" : msUntilDue < windowMs * DUE_SOON_FRACTION ? "due_soon" : "on_time";
  return { phase: responded ? "resolution" : "response", due, windowMs, msUntilDue, level };
}

/** Re-renders the caller every `intervalMs` so "overdue by 3 hours" and the
 * on-time → overdue flip stay current on a page left open. */
export function useNow(intervalMs = 60_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);
  return now;
}

function plural(n: number, unit: string): string {
  return `${n} ${unit}${n === 1 ? "" : "s"}`;
}

// Coarse on purpose: nobody needs "2 days 3 hours 12 minutes" to know whether
// a ticket is late.
function durationParts(ms: number): { value: number; unit: "minute" | "hour" | "day" } | null {
  const minutes = Math.floor(Math.abs(ms) / 60_000);
  if (minutes < 1) return null;
  if (minutes < 60) return { value: minutes, unit: "minute" };
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return { value: hours, unit: "hour" };
  return { value: Math.floor(hours / 24), unit: "day" };
}

/** "3 hours", "2 days", "less than a minute". Sign is ignored. */
export function formatDuration(ms: number): string {
  const parts = durationParts(ms);
  return parts ? plural(parts.value, parts.unit) : "less than a minute";
}

/** "3h", "2d", "<1m" — for table cells. Sign is ignored. */
export function formatDurationShort(ms: number): string {
  const parts = durationParts(ms);
  return parts ? `${parts.value}${parts.unit[0]}` : "<1m";
}

/** "Within 4 hours" / "Within 1 day" for a window length. */
export function formatWindow(ms: number): string {
  const hours = Math.round(ms / 3_600_000);
  if (hours >= 24 && hours % 24 === 0) return `Within ${plural(hours / 24, "day")}`;
  return `Within ${plural(Math.max(hours, 1), "hour")}`;
}

/** "Today, 2:30 PM" / "Tomorrow, 2:30 PM" / "Wed, Sep 23, 2:30 PM". */
export function formatDueAt(date: Date, now: number = Date.now()): string {
  const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const dayDiff = Math.round((startOfDay(date) - startOfDay(new Date(now))) / 86_400_000);
  if (dayDiff === 0) return `Today, ${time}`;
  if (dayDiff === 1) return `Tomorrow, ${time}`;
  if (dayDiff === -1) return `Yesterday, ${time}`;
  const day = date.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
  return `${day}, ${time}`;
}
