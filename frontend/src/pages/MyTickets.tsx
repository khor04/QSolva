import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { usePagination } from "@/lib/usePagination";
import type { Ticket } from "@/lib/types";
import { StatusBadge, PriorityBadge } from "@/components/Badge";
import { PaginationControls } from "@/components/PaginationControls";

const PAGE_SIZE = 10;

function TicketTable({ tickets }: { tickets: Ticket[] }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border-warm bg-white">
      <table className="w-full table-fixed text-left text-sm">
        <colgroup>
          <col className="w-[50%]" />
          <col className="w-[15%]" />
          <col className="w-[15%]" />
          <col className="w-[20%]" />
        </colgroup>
        <thead className="border-b border-border-warm bg-cream text-neutral-500">
          <tr>
            <th className="px-4 py-2 font-medium">Title</th>
            <th className="px-4 py-2 font-medium">Priority</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Updated</th>
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
              <td className="px-4 py-3"><StatusBadge status={ticket.status} /></td>
              <td className="truncate px-4 py-3 text-neutral-500">
                {new Date(ticket.updated_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MyTickets() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["tickets", "mine"],
    queryFn: () => api.get<Ticket[]>("/tickets"),
  });

  const active = data?.filter((t) => t.status !== "closed") ?? [];
  const history = data?.filter((t) => t.status === "closed") ?? [];

  const activePage = usePagination(active, PAGE_SIZE);
  const historyPage = usePagination(history, PAGE_SIZE);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">My Tickets</h1>
        <Link
          to="/tickets/new"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white"
        >
          + New Ticket
        </Link>
      </div>

      {isLoading && <p className="text-sm text-neutral-500">Loading...</p>}
      {error && <p className="text-sm text-red-600">Failed to load tickets.</p>}

      {data && data.length === 0 && (
        <p className="text-sm text-neutral-500">No tickets yet. Create one to get started.</p>
      )}

      {active.length > 0 && (
        <div className="mb-8">
          <TicketTable tickets={activePage.pageItems} />
          <PaginationControls
            page={activePage.page}
            totalPages={activePage.totalPages}
            totalItems={activePage.totalItems}
            onChange={activePage.setPage}
          />
        </div>
      )}
      {data && data.length > 0 && active.length === 0 && (
        <p className="mb-8 text-sm text-neutral-500">No active tickets right now.</p>
      )}

      {history.length > 0 && (
        <div>
          <h2 className="mb-3 text-sm font-medium text-neutral-500">History</h2>
          <TicketTable tickets={historyPage.pageItems} />
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
