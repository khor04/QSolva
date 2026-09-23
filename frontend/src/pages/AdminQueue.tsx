import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { usePagination } from "@/lib/usePagination";
import { TICKET_CATEGORIES, type Ticket, type TicketCategory, type TicketPriority } from "@/lib/types";
import { StatusBadge, PriorityBadge } from "@/components/Badge";
import { PaginationControls } from "@/components/PaginationControls";
import { TeamWorkload } from "@/components/TeamWorkload";
import { formatDurationShort, getSla, useNow } from "@/lib/sla";

type Filter = "open" | "unassigned" | "mine" | "critical" | "overdue";
const FILTERS: Filter[] = ["open", "unassigned", "mine", "critical", "overdue"];
const PAGE_SIZE = 10;
const PRIORITY_RANK: Record<TicketPriority, number> = { critical: 4, high: 3, medium: 2, low: 1 };

// Overdue against the ticket's own SLA deadline (first response until an admin
// picks it up, then resolution). Resolved/closed tickets aren't waiting on an
// admin, so getSla never reports them as overdue.
function isOverdue(t: Ticket, now: number): boolean {
  return getSla(t, now).level === "overdue";
}

const IDLE_MS = 24 * 60 * 60 * 1000;

// An admin replied last and nothing's moved since — the ball is in the
// staff member's court, or the admin forgot to close it out. Distinct from
// SLA overdue: this can't fire on a ticket nobody has touched yet.
function isIdle(t: Ticket, now: number): boolean {
  return (
    t.status === "in_progress" &&
    t.last_message_by === "admin" &&
    !!t.last_message_at &&
    now - new Date(t.last_message_at).getTime() > IDLE_MS
  );
}

function SlaCell({ ticket, now }: { ticket: Ticket; now: number }) {
  const sla = getSla(ticket, now);
  if (sla.level === null) return <span className="text-neutral-400">—</span>;
  const what = sla.phase === "response" ? "Response" : "Resolution";
  const time = formatDurationShort(sla.msUntilDue);
  if (sla.level === "overdue") {
    return <span className="font-medium text-red-700">🔴 {what} overdue by {time}</span>;
  }
  if (sla.level === "due_soon") {
    return <span className="font-medium text-orange-700">🟠 {what} due in {time}</span>;
  }
  return <span className="text-green-700">🟢 {what} due in {time}</span>;
}

// Overdue tickets always surface first, then most urgent priority, then
// whichever has gone longest without an update within the same tier — so
// nothing urgent gets buried and nothing stale gets forgotten.
function sortQueue(tickets: Ticket[], now: number): Ticket[] {
  return [...tickets].sort((a, b) => {
    const overdueDiff = Number(isOverdue(b, now)) - Number(isOverdue(a, now));
    if (overdueDiff !== 0) return overdueDiff;
    const priorityDiff = PRIORITY_RANK[b.priority] - PRIORITY_RANK[a.priority];
    if (priorityDiff !== 0) return priorityDiff;
    return new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime();
  });
}

const SEARCH_DEBOUNCE_MS = 300;

// The date inputs give "YYYY-MM-DD" in the admin's local calendar; convert to
// local-midnight instants so "Mar 1 – Mar 31" means their March, not UTC's.
function startOfLocalDay(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d).toISOString();
}

function startOfNextLocalDay(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y, m - 1, d + 1).toISOString();
}

function QueueTable({ tickets, currentAdminId, now }: { tickets: Ticket[]; currentAdminId?: string; now: number }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border-warm bg-white">
      <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] table-fixed text-left text-sm">
        <colgroup>
          <col className="w-[27%]" />
          <col className="w-[10%]" />
          <col className="w-[11%]" />
          <col className="w-[20%]" />
          <col className="w-[16%]" />
          <col className="w-[16%]" />
        </colgroup>
        <thead className="border-b border-border-warm bg-cream text-neutral-500">
          <tr>
            <th className="px-4 py-2 font-medium">Title</th>
            <th className="px-4 py-2 font-medium">Priority</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">SLA</th>
            <th className="px-4 py-2 font-medium">Assigned</th>
            <th className="px-4 py-2 font-medium">Updated</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket) => {
            const overdue = isOverdue(ticket, now);
            return (
              <tr
                key={ticket.id}
                className={`border-b border-primary-light/40 last:border-0 ${
                  overdue ? "bg-red-50 hover:bg-red-100" : "hover:bg-primary-light/20"
                }`}
              >
                <td className="px-4 py-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <Link
                      to={`/tickets/${ticket.id}`}
                      className="min-w-0 flex-1 truncate font-medium text-primary-dark hover:underline"
                    >
                      {ticket.title}
                    </Link>
                    {isIdle(ticket, now) && (
                      <span
                        title="An admin replied over 24h ago and the ticket hasn't moved since"
                        className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
                      >
                        ⚠️ Awaiting staff
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3"><PriorityBadge priority={ticket.priority} /></td>
                <td className="px-4 py-3"><StatusBadge status={ticket.status} /></td>
                <td className="px-4 py-3 text-xs"><SlaCell ticket={ticket} now={now} /></td>
                <td className="truncate px-4 py-3 text-neutral-500">
                  {ticket.assigned_admin_id
                    ? ticket.assigned_admin_id === currentAdminId
                      ? "You"
                      : ticket.assigned_admin_name ?? "Unknown admin"
                    : ticket.status === "escalated" && ticket.escalated_by_admin_id
                      ? `Escalated by ${ticket.escalated_by_admin_id === currentAdminId ? "you" : ticket.escalated_by_admin_name ?? "unknown admin"}`
                      : "Unassigned"}
                </td>
                <td className="truncate px-4 py-3 text-neutral-500">
                  {new Date(ticket.updated_at).toLocaleString()}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
    </div>
  );
}

function waitingSince(resolvedAt: string | null): string {
  if (!resolvedAt) return "—";
  const days = Math.floor((Date.now() - new Date(resolvedAt).getTime()) / (24 * 60 * 60 * 1000));
  if (days <= 0) return "Today";
  return `${days} day${days === 1 ? "" : "s"}`;
}

function ResolvedTable({ tickets }: { tickets: Ticket[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border-warm bg-white">
      <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] table-fixed text-left text-sm">
        <colgroup>
          <col className="w-[55%]" />
          <col className="w-[20%]" />
          <col className="w-[25%]" />
        </colgroup>
        <thead className="border-b border-border-warm bg-cream text-neutral-500">
          <tr>
            <th className="px-4 py-2 font-medium">Title</th>
            <th className="px-4 py-2 font-medium">Priority</th>
            <th className="px-4 py-2 font-medium">Waiting since</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket) => (
            <tr key={ticket.id} className="border-b border-primary-light/40 last:border-0 hover:bg-primary-light/20">
              <td className="truncate px-4 py-3">
                <Link to={`/tickets/${ticket.id}`} className="font-medium text-primary-dark hover:underline">
                  {ticket.title}
                </Link>
              </td>
              <td className="px-4 py-3"><PriorityBadge priority={ticket.priority} /></td>
              <td className="truncate px-4 py-3 text-neutral-500">{waitingSince(ticket.resolved_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}

export function AdminQueue() {
  const { profile } = useAuth();
  const now = useNow();
  const [activeFilters, setActiveFilters] = useState<Set<Filter>>(new Set());
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [category, setCategory] = useState<TicketCategory | "">("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  // Search, category and date range are applied by the API (search covers
  // descriptions and resolutions, which aren't in the list payload); the
  // status chips below stay client-side since they're instant on loaded data.
  const { data, isLoading, error } = useQuery({
    queryKey: ["tickets", "queue", { q: debouncedSearch, category, dateFrom, dateTo }],
    queryFn: () => {
      const params = new URLSearchParams();
      if (debouncedSearch) params.set("q", debouncedSearch);
      if (category) params.set("category", category);
      if (dateFrom) params.set("created_after", startOfLocalDay(dateFrom));
      if (dateTo) params.set("created_before", startOfNextLocalDay(dateTo));
      const qs = params.toString();
      return api.get<Ticket[]>(`/tickets/queue${qs ? `?${qs}` : ""}`);
    },
    placeholderData: keepPreviousData,
  });

  const hasSearchFilters = search !== "" || category !== "" || dateFrom !== "" || dateTo !== "";

  const matchesFilters = (t: Ticket) => {
    if (activeFilters.size === 0) return true;
    // OR across selected chips: a ticket matches if it satisfies any of them.
    return (
      (activeFilters.has("open") && t.status === "open") ||
      (activeFilters.has("unassigned") && !t.assigned_admin_id) ||
      (activeFilters.has("mine") && t.assigned_admin_id === profile?.id) ||
      (activeFilters.has("critical") && t.priority === "critical") ||
      (activeFilters.has("overdue") && isOverdue(t, now))
    );
  };

  const filtered = useMemo(() => {
    return (data ?? []).filter(matchesFilters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, activeFilters, profile?.id, now]);

  const active = sortQueue(filtered.filter((t) => t.status !== "closed" && t.status !== "resolved"), now);
  const awaitingConfirmation = filtered.filter((t) => t.status === "resolved");
  const history = filtered.filter((t) => t.status === "closed");

  const activePage = usePagination(active, PAGE_SIZE);
  const awaitingPage = usePagination(awaitingConfirmation, PAGE_SIZE);
  const historyPage = usePagination(history, PAGE_SIZE);

  function resetPages() {
    activePage.setPage(1);
    awaitingPage.setPage(1);
    historyPage.setPage(1);
  }

  function clearSearchFilters() {
    setSearch("");
    setDebouncedSearch("");
    setCategory("");
    setDateFrom("");
    setDateTo("");
    resetPages();
  }

  function toggleFilter(f: Filter) {
    resetPages();
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(f)) next.delete(f);
      else next.add(f);
      return next;
    });
  }

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold">Ticket Queue</h1>

      <TeamWorkload />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            resetPages();
          }}
          placeholder="Search title, description, resolution..."
          aria-label="Search tickets"
          className="w-full max-w-xs rounded-md border border-border-warm px-3 py-1.5 text-sm sm:w-72"
        />
        <select
          value={category}
          onChange={(e) => {
            setCategory(e.target.value as TicketCategory | "");
            resetPages();
          }}
          aria-label="Category"
          className="rounded-md border border-border-warm px-3 py-1.5 text-sm capitalize"
        >
          <option value="">All categories</option>
          {TICKET_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c.replace("_", " ")}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-sm text-neutral-500">
          From
          <input
            type="date"
            value={dateFrom}
            max={dateTo || undefined}
            onChange={(e) => {
              setDateFrom(e.target.value);
              resetPages();
            }}
            className="rounded-md border border-border-warm px-2 py-1 text-sm text-neutral-800"
          />
        </label>
        <label className="flex items-center gap-1.5 text-sm text-neutral-500">
          To
          <input
            type="date"
            value={dateTo}
            min={dateFrom || undefined}
            onChange={(e) => {
              setDateTo(e.target.value);
              resetPages();
            }}
            className="rounded-md border border-border-warm px-2 py-1 text-sm text-neutral-800"
          />
        </label>
        {hasSearchFilters && (
          <button onClick={clearSearchFilters} className="text-sm text-primary-dark hover:underline">
            Clear
          </button>
        )}
        <div className="flex gap-2 text-sm">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => toggleFilter(f)}
              className={`rounded-full px-3 py-1 capitalize ${
                activeFilters.has(f)
                  ? "bg-primary text-white"
                  : "bg-primary-light/20 text-neutral-600 hover:bg-primary-light/40"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {isLoading && <p className="text-sm text-neutral-500">Loading...</p>}
      {error && <p className="text-sm text-red-600">Failed to load queue.</p>}

      {data && filtered.length === 0 && (
        <p className="text-sm text-neutral-500">No tickets match this filter.</p>
      )}

      {filtered.length > 0 && (
        <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
          <div>
            <h2 className="mb-3 text-sm font-medium text-neutral-500">Active</h2>
            {active.length > 0 ? (
              <>
                <QueueTable tickets={activePage.pageItems} currentAdminId={profile?.id} now={now} />
                <PaginationControls
                  page={activePage.page}
                  totalPages={activePage.totalPages}
                  totalItems={activePage.totalItems}
                  onChange={activePage.setPage}
                />
              </>
            ) : (
              <p className="text-sm text-neutral-500">No active tickets match this filter.</p>
            )}
          </div>

          <div>
            <h2 className="mb-3 text-sm font-medium text-neutral-500">Awaiting Confirmation</h2>
            {awaitingConfirmation.length > 0 ? (
              <>
                <ResolvedTable tickets={awaitingPage.pageItems} />
                <PaginationControls
                  page={awaitingPage.page}
                  totalPages={awaitingPage.totalPages}
                  totalItems={awaitingPage.totalItems}
                  onChange={awaitingPage.setPage}
                />
              </>
            ) : (
              <p className="text-sm text-neutral-500">Nothing waiting on staff confirmation.</p>
            )}
          </div>
        </div>
      )}

      {history.length > 0 && (
        <div>
          <h2 className="mb-3 text-sm font-medium text-neutral-500">History</h2>
          <QueueTable tickets={historyPage.pageItems} currentAdminId={profile?.id} now={now} />
          <PaginationControls
            page={historyPage.page}
            totalPages={historyPage.totalPages}
            totalItems={historyPage.totalItems}
            onChange={historyPage.setPage}
          />
        </div>
      )}
    </div>
  );
}
