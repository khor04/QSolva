import { useState, type ReactNode } from "react";
import {
  formatDueAt,
  formatDuration,
  formatWindow,
  getSla,
  useNow,
  type SlaLevel,
  type SlaState,
} from "@/lib/sla";
import type { Ticket, TicketStatus } from "@/lib/types";

const STEPS = ["Submitted", "In progress", "Resolved", "Closed"] as const;

// escalated = released back to the queue with no owner, so it sits at the
// same step as a brand-new ticket.
const STEP_FOR_STATUS: Record<TicketStatus, number> = {
  open: 0,
  escalated: 0,
  in_progress: 1,
  resolved: 2,
  closed: 3,
};

type Tone = "ok" | "soon" | "late" | "neutral";

const TONE_CLASSES: Record<Tone, string> = {
  ok: "border-green-200 bg-green-50 text-green-900",
  soon: "border-amber-200 bg-amber-50 text-amber-900",
  late: "border-red-200 bg-red-50 text-red-800",
  neutral: "border-border-warm bg-cream text-neutral-700",
};

function toneFor(level: SlaLevel | null): Tone {
  if (level === "overdue") return "late";
  if (level === "due_soon") return "soon";
  return level === "on_time" ? "ok" : "neutral";
}

export interface AdminControls {
  onStart: () => void;
  onResolve: () => void;
  busy: boolean;
}

function Stepper({
  ticket,
  admin,
  onRequestResolve,
}: {
  ticket: Ticket;
  admin?: AdminControls;
  onRequestResolve: () => void;
}) {
  const current = STEP_FOR_STATUS[ticket.status];
  const closed = ticket.status === "closed";
  const active = ticket.status !== "resolved" && !closed;

  // Admins can move the ticket forward from the tracker itself: claiming it
  // is what starts work, and Resolved asks the staff member to confirm.
  // Closed stays staff-only — it's their confirmation, not the admin's call.
  function actionFor(step: number): { title: string; run: () => void } | null {
    if (!admin || !active) return null;
    if (step === 1 && !ticket.assigned_admin_id) {
      return { title: "Claim this ticket and start work", run: admin.onStart };
    }
    if (step === 2) return { title: "Mark as resolved", run: onRequestResolve };
    return null;
  }

  return (
    <ol className="flex items-center overflow-x-auto">
      {STEPS.map((label, i) => {
        const done = i < current || closed;
        const isCurrent = i === current && !closed;
        const action = actionFor(i);
        const dot = (
          <span
            className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 text-[8px] font-bold sm:h-5 sm:w-5 sm:text-[10px] ${
              done
                ? "border-primary bg-primary text-white"
                : isCurrent
                  ? "border-primary bg-white ring-4 ring-primary-light/40"
                  : action
                    ? "border-dashed border-primary bg-white"
                    : "border-border-warm bg-white"
            }`}
          >
            {done ? "✓" : ""}
          </span>
        );
        const text = (
          <span
            className={`whitespace-nowrap text-[10px] sm:text-sm ${
              isCurrent ? "font-semibold text-neutral-900" : done ? "text-neutral-700" : "text-neutral-400"
            }`}
          >
            {label}
          </span>
        );
        return (
          <li key={label} className="flex shrink-0 items-center sm:flex-1 sm:last:flex-none">
            {action ? (
              <button
                onClick={action.run}
                disabled={admin?.busy}
                title={action.title}
                className="flex items-center gap-1 rounded-md py-1 pr-0 hover:bg-primary-light/20 disabled:opacity-50 sm:gap-2 sm:pr-1"
              >
                {dot}
                {text}
              </button>
            ) : (
              <span className="flex items-center gap-1 py-1 pr-0 sm:gap-2 sm:pr-1">
                {dot}
                {text}
              </span>
            )}
            {i < STEPS.length - 1 && (
              <span className={`mx-1 h-0.5 w-3 rounded sm:mx-2 sm:w-auto sm:flex-1 ${i < current || closed ? "bg-primary" : "bg-border-warm"}`} />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function Message({ tone, title, children }: { tone: Tone; title: string; children?: ReactNode }) {
  return (
    <div className={`mt-4 rounded-md border px-3 py-2.5 ${TONE_CLASSES[tone]}`}>
      <p className="text-sm font-medium">{title}</p>
      {children && <div className="mt-0.5 text-sm">{children}</div>}
    </div>
  );
}

// Staff only need to know the next thing they're waiting for, in plain words —
// not a table of deadlines and not what "overdue" means.
function StaffStatus({ ticket, sla, now }: { ticket: Ticket; sla: SlaState; now: number }) {
  if (sla.phase === "closed") {
    return <Message tone="neutral" title="This ticket is closed" />;
  }
  if (sla.phase === "awaiting_confirmation") {
    return (
      <Message tone="soon" title="Waiting for your confirmation">
        Please confirm whether the solution worked.
      </Message>
    );
  }

  const due = sla.due!;
  const overdue = sla.level === "overdue";
  const admin = ticket.assigned_admin_name ?? "An admin";

  if (sla.phase === "response") {
    if (overdue) {
      // Soft, action-oriented wording for staff — a bare "Overdue by 3h" reads
      // as "you've been ignored" even mid-outage. Admins still see the exact
      // number in AdminSla below, since they're the ones who have to act on it.
      return (
        <Message tone="soon" title="⚠️ Taking longer than usual">
          This is past our usual first-response time. It's been flagged internally to speed it up.
        </Message>
      );
    }
    return (
      <Message tone="neutral" title="⏱ Expected first response">
        {formatWindow(sla.windowMs)} · {formatDueAt(due, now)}
      </Message>
    );
  }

  // Resolution phase: someone already picked it up, though it may have since
  // been released back to the queue.
  const headline = ticket.assigned_admin_id ? `${admin} is working on your ticket` : "Waiting for an admin to take over";
  if (overdue) {
    return (
      <Message tone="soon" title="⚠️ Taking longer than usual">
        {ticket.assigned_admin_id
          ? `${admin} is still on it — it's been flagged internally to speed it up.`
          : "It's back in the queue, and flagged internally to speed it up."}
      </Message>
    );
  }
  return (
    <Message tone="neutral" title={headline}>
      Expected resolution: {formatWindow(sla.windowMs)} · {formatDueAt(due, now)}
    </Message>
  );
}

function SlaRow({ label, tone, children }: { label: string; tone: Tone; children: ReactNode }) {
  return (
    <div className={`rounded-md border px-3 py-2 ${TONE_CLASSES[tone]}`}>
      <p className="text-xs font-medium uppercase tracking-wide opacity-70">{label}</p>
      <div className="mt-0.5 text-sm">{children}</div>
    </div>
  );
}

function levelLine(level: SlaLevel | null, msUntilDue: number): string {
  if (level === "overdue") return `🔴 Overdue by ${formatDuration(msUntilDue)}`;
  if (level === "due_soon") return `🟠 Due soon — ${formatDuration(msUntilDue)} remaining`;
  return `🟢 On time — ${formatDuration(msUntilDue)} remaining`;
}

// Admins get both deadlines, since they're the ones who have to hit them.
function AdminSla({ ticket, sla, now }: { ticket: Ticket; sla: SlaState; now: number }) {
  const responded = ticket.first_response_at != null;
  const finished = sla.phase === "awaiting_confirmation" || sla.phase === "closed";
  const responseDue = new Date(ticket.response_due_at);
  const resolutionDue = new Date(ticket.resolution_due_at);

  let response: ReactNode;
  let responseTone: Tone;
  if (responded) {
    const at = new Date(ticket.first_response_at!);
    const lateBy = at.getTime() - responseDue.getTime();
    responseTone = lateBy > 0 ? "soon" : "ok";
    response = (
      <>
        ✓ Responded {formatDueAt(at, now)} — {lateBy > 0 ? `${formatDuration(lateBy)} late` : "on time"}
      </>
    );
  } else {
    responseTone = toneFor(sla.level);
    response = (
      <>
        <p>Due: {formatDueAt(responseDue, now)}</p>
        <p>{levelLine(sla.level, sla.msUntilDue)}</p>
        {sla.level === "overdue" && <p>No admin response yet</p>}
      </>
    );
  }

  let resolution: ReactNode;
  let resolutionTone: Tone = "neutral";
  if (finished) {
    const at = ticket.resolved_at ? new Date(ticket.resolved_at) : null;
    const lateBy = at ? at.getTime() - resolutionDue.getTime() : 0;
    resolutionTone = at && lateBy > 0 ? "soon" : "ok";
    resolution = at
      ? `✓ Resolved ${formatDueAt(at, now)} — ${lateBy > 0 ? `${formatDuration(lateBy)} late` : "on time"}`
      : "✓ Closed";
  } else if (!responded) {
    resolution = (
      <>
        <p>⏳ Not started</p>
        <p>Due: {formatDueAt(resolutionDue, now)}</p>
      </>
    );
  } else {
    resolutionTone = toneFor(sla.level);
    resolution = (
      <>
        <p>Due: {formatDueAt(resolutionDue, now)}</p>
        <p>{levelLine(sla.level, sla.msUntilDue)}</p>
      </>
    );
  }

  return (
    <div className="mt-4">
      <h3 className="mb-2 text-sm font-medium text-neutral-500">SLA</h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <SlaRow label="First response" tone={responseTone}>{response}</SlaRow>
        <SlaRow label="Resolution" tone={resolutionTone}>{resolution}</SlaRow>
      </div>
    </div>
  );
}

export function TicketProgress({ ticket, admin }: { ticket: Ticket; admin?: AdminControls }) {
  const now = useNow();
  const sla = getSla(ticket, now);
  const [confirmingResolve, setConfirmingResolve] = useState(false);

  return (
    <div className="mb-6 rounded-lg border border-border-warm bg-white p-4">
      <Stepper ticket={ticket} admin={admin} onRequestResolve={() => setConfirmingResolve(true)} />

      {admin && confirmingResolve && (
        <div className="mt-4 rounded-md border border-primary-light/50 bg-primary-light/10 p-3">
          <p className="mb-3 text-sm">Mark this ticket as resolved? The staff member will be asked to confirm.</p>
          <div className="flex gap-2">
            <button
              onClick={() => {
                admin.onResolve();
                setConfirmingResolve(false);
              }}
              disabled={admin.busy}
              className="rounded-md bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700 disabled:opacity-50"
            >
              Mark resolved
            </button>
            <button
              onClick={() => setConfirmingResolve(false)}
              className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {admin ? <AdminSla ticket={ticket} sla={sla} now={now} /> : <StaffStatus ticket={ticket} sla={sla} now={now} />}
    </div>
  );
}
