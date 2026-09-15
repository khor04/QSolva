import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { usePagination } from "@/lib/usePagination";
import type { Ticket, TicketPriority } from "@/lib/types";
import { StatusBadge, PriorityBadge } from "@/components/Badge";
import { PaginationControls } from "@/components/PaginationControls";

type Filter = "open" | "unassigned" | "mine" | "critical";
const FILTERS: Filter[] = ["open", "unassigned", "mine", "critical"];
const PAGE_SIZE = 10;
const OVERDUE_MS = 5 * 24 * 60 * 60 * 1000;
const PRIORITY_RANK: Record<TicketPriority, number> = { critical: 4, high: 3, medium: 2, low: 1 };

function isOverdue(t: Ticket): boolean {
  // Once resolved, it's waiting on the staff member to confirm — not on the
  // admin — so it shouldn't be flagged as something the admin is neglecting.
  return (
    t.status !== "closed" &&
    t.status !== "resolved" &&
    Date.now() - new Date(t.created_at).getTime() > OVERDUE_MS
  );
}

// Overdue tickets always surface first, then most urgent priority, then
// whichever has gone longest without an update within the same tier — so
// nothing urgent gets buried and nothing stale gets forgotten.
function sortQueue(tickets: Ticket[]): Ticket[] {
  return [...tickets].sort((a, b) => {
    const overdueDiff = Number(isOverdue(b)) - Number(isOverdue(a));
    if (overdueDiff !== 0) return overdueDiff;
    const priorityDiff = PRIORITY_RANK[b.priority] - PRIORITY_RANK[a.priority];
    if (priorityDiff !== 0) return priorityDiff;
    return new Date(a.updated_at).getTime() - new Date(b.updated_at).getTime();
  });
}

function QueueTable({ tickets, currentAdminId }: { tickets: Ticket[]; currentAdminId?: string }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border-warm bg-white">
      <table className="w-full table-fixed text-left text-sm">
        <colgroup>
          <col className="w-[38%]" />
          <col className="w-[13%]" />
          <col className="w-[13%]" />
          <col className="w-[18%]" />
          <col className="w-[18%]" />
        </colgroup>
        <thead className="border-b border-border-warm bg-cream text-neutral-500">
          <tr>
            <th className="px-4 py-2 font-medium">Title</th>
            <th className="px-4 py-2 font-medium">Priority</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Assigned</th>
            <th className="px-4 py-2 font-medium">Updated</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket) => {
            const overdue = isOverdue(ticket);
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
                    {overdue && (
                      <span className="shrink-0 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                        Overdue
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3"><PriorityBadge priority={ticket.priority} /></td>
                <td className="px-4 py-3"><StatusBadge status={ticket.status} /></td>
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
      <table className="w-full table-fixed text-left text-sm">
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
  );
}

export function AdminQueue() {
  const { profile } = useAuth();
  const [activeFilters, setActiveFilters] = useState<Set<Filter>>(new Set());
  const [search, setSearch] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["tickets", "queue"],
    queryFn: () => api.get<Ticket[]>("/tickets/queue"),
  });

  const matchesFilters = (t: Ticket) => {
    if (activeFilters.size === 0) return true;
    // OR across selected chips: a ticket matches if it satisfies any of them.
    return (
      (activeFilters.has("open") && t.status === "open") ||
      (activeFilters.has("unassigned") && !t.assigned_admin_id) ||
      (activeFilters.has("mine") && t.assigned_admin_id === profile?.id) ||
      (activeFilters.has("critical") && t.priority === "critical")
    );
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (data ?? []).filter((t) => matchesFilters(t) && (q === "" || t.title.toLowerCase().includes(q)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, activeFilters, search, profile?.id]);

  const active = sortQueue(filtered.filter((t) => t.status !== "closed" && t.status !== "resolved"));
  const awaitingConfirmation = filtered.filter((t) => t.status === "resolved");
  const history = filtered.filter((t) => t.status === "closed");

  const activePage = usePagination(active, PAGE_SIZE);
  const awaitingPage = usePagination(awaitingConfirmation, PAGE_SIZE);
  const historyPage = usePagination(history, PAGE_SIZE);

  function toggleFilter(f: Filter) {
    activePage.setPage(1);
    awaitingPage.setPage(1);
    historyPage.setPage(1);
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

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            activePage.setPage(1);
            awaitingPage.setPage(1);
            historyPage.setPage(1);
          }}
          placeholder="Search tickets by title..."
          className="w-full max-w-xs rounded-md border border-border-warm px-3 py-1.5 text-sm sm:w-64"
        />
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
                <QueueTable tickets={activePage.pageItems} currentAdminId={profile?.id} />
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
          <QueueTable tickets={historyPage.pageItems} currentAdminId={profile?.id} />
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
