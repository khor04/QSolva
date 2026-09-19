import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminWorkload } from "@/lib/types";

export function TeamWorkload() {
  const { profile } = useAuth();
  const { data } = useQuery({
    queryKey: ["admin", "workload"],
    queryFn: () => api.get<AdminWorkload[]>("/admin/workload"),
    // Claims happen from other browsers too, so keep the numbers fresh.
    refetchInterval: 30_000,
  });

  if (!data || data.length === 0) return null;

  // Bars are scaled against the busiest admin, so "who's overloaded vs idle"
  // reads at a glance without inventing a workload score.
  const max = Math.max(...data.map((a) => a.active_tickets), 1);

  return (
    <section className="mb-6 rounded-lg border border-border-warm bg-white p-4">
      <h2 className="mb-3 text-sm font-medium text-neutral-500">Team Workload</h2>
      <ul className="space-y-2">
        {data.map((admin) => (
          <li key={admin.id} className="grid grid-cols-[8rem_1fr_auto] items-center gap-3 text-sm">
            <span className="truncate font-medium">
              {admin.name}
              {admin.id === profile?.id && <span className="font-normal text-neutral-400"> (you)</span>}
            </span>
            <div className="h-2 rounded-full bg-primary-light/20">
              <div
                className="h-2 rounded-full bg-primary"
                style={{ width: `${(admin.active_tickets / max) * 100}%` }}
              />
            </div>
            <span className="whitespace-nowrap text-neutral-500">
              {admin.active_tickets} active · {admin.high_critical_tickets} high/critical ·{" "}
              <span className={admin.overdue_tickets > 0 ? "font-medium text-red-600" : ""}>
                {admin.overdue_tickets} overdue
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
