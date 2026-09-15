import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { IssueSeverity } from "@/lib/types";

interface PriorityDistribution {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

interface DashboardTrendPoint {
  date: string;
  count: number;
}

interface DashboardEmergingIssue {
  id: string;
  label: string;
  tickets_this_week: number;
  pct_change: number | null;
  severity: IssueSeverity;
}

interface AiPerformance {
  acceptance_rate: number | null;
  coverage_rate: number | null;
  deflection_rate: number | null;
}

interface DashboardStats {
  total_tickets: number;
  open_tickets: number;
  overdue_tickets: number;
  resolved_tickets: number;
  closed_tickets: number;
  recurring_issues_count: number;
  priority_distribution: PriorityDistribution;
  volume_trend: DashboardTrendPoint[];
  emerging_issues: DashboardEmergingIssue[];
  ai_performance: AiPerformance;
}

const SEVERITY_ICON: Record<IssueSeverity, string> = {
  emerging: "🔴",
  elevated: "🟠",
  watch: "🟡",
};

function pct(value: number | null): string {
  return value != null ? `${Math.round(value * 100)}%` : "—";
}

function MiniBarChart({ bars }: { bars: { label: string; count: number; colorClass?: string }[] }) {
  const max = Math.max(1, ...bars.map((b) => b.count));
  return (
    <div className="flex items-end gap-1" style={{ height: 100 }}>
      {bars.map((b) => (
        <div key={b.label} className="flex flex-1 flex-col items-center gap-1" title={`${b.label}: ${b.count}`}>
          <div
            className={`w-full rounded-t ${b.colorClass ?? "bg-primary/70"}`}
            style={{ height: `${Math.max(4, (b.count / max) * 80)}px` }}
          />
          <span className="max-w-full truncate text-[9px] text-neutral-400">{b.label}</span>
        </div>
      ))}
    </div>
  );
}

export function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: () => api.get<DashboardStats>("/dashboard/stats"),
  });

  return (
    <div>
      <h1 className="mb-6 text-xl font-semibold">Service Desk Overview</h1>
      {isLoading && <p className="text-sm text-neutral-500">Loading...</p>}
      {error && <p className="text-sm text-red-600">Failed to load dashboard stats.</p>}

      {data && (
        <>
          <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-4">
            <div className="rounded-lg border border-border-warm bg-white p-4 md:col-span-2">
              <p className="text-2xl font-semibold">{data.total_tickets}</p>
              <p className="mb-3 text-sm text-neutral-500">Total Tickets</p>
              <div className="grid grid-cols-4 gap-2 border-t border-primary-light/40 pt-3 text-center">
                <div>
                  <p className="text-lg font-medium">{data.open_tickets}</p>
                  <p className="text-xs text-neutral-500">Open</p>
                </div>
                <div>
                  <p className={`text-lg font-medium ${data.overdue_tickets > 0 ? "text-red-600" : ""}`}>
                    {data.overdue_tickets}
                  </p>
                  <p className="text-xs text-neutral-500">Overdue</p>
                </div>
                <div>
                  <p className="text-lg font-medium">{data.resolved_tickets}</p>
                  <p className="text-xs text-neutral-500">Resolved</p>
                </div>
                <div>
                  <p className="text-lg font-medium">{data.closed_tickets}</p>
                  <p className="text-xs text-neutral-500">Closed</p>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-border-warm bg-white p-4">
              <p className="text-2xl font-semibold">{pct(data.ai_performance.acceptance_rate)}</p>
              <p className="text-sm text-neutral-500">AI Acceptance Rate</p>
            </div>

            <div className="rounded-lg border border-border-warm bg-white p-4">
              <p className="text-2xl font-semibold">{data.recurring_issues_count}</p>
              <p className="text-sm text-neutral-500">Recurring Issues</p>
            </div>
          </div>

          <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-border-warm bg-white p-4">
              <h2 className="mb-3 text-sm font-medium text-neutral-500">Ticket Volume (last 14 days)</h2>
              <MiniBarChart
                bars={data.volume_trend.map((p) => ({ label: p.date.slice(5), count: p.count }))}
              />
            </div>

            <div className="rounded-lg border border-border-warm bg-white p-4">
              <h2 className="mb-3 text-sm font-medium text-neutral-500">Priority Distribution</h2>
              <MiniBarChart
                bars={[
                  { label: "Critical", count: data.priority_distribution.critical, colorClass: "bg-red-400" },
                  { label: "High", count: data.priority_distribution.high, colorClass: "bg-orange-400" },
                  { label: "Medium", count: data.priority_distribution.medium, colorClass: "bg-amber-300" },
                  { label: "Low", count: data.priority_distribution.low, colorClass: "bg-neutral-300" },
                ]}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-border-warm bg-white p-4">
              <h2 className="mb-3 text-sm font-medium text-neutral-500">Emerging Issues</h2>
              {data.emerging_issues.length === 0 && (
                <p className="text-sm text-neutral-400">No recurring issues yet.</p>
              )}
              <div className="space-y-2">
                {data.emerging_issues.map((issue) => (
                  <Link
                    key={issue.id}
                    to={`/issues/${issue.id}`}
                    className="flex items-center justify-between rounded-md border border-primary-light/40 px-3 py-2 text-sm hover:bg-primary-light/20"
                  >
                    <span>
                      {SEVERITY_ICON[issue.severity]} {issue.label}
                    </span>
                    <span className="text-neutral-500">
                      {issue.tickets_this_week} tickets
                      {issue.pct_change != null && ` (${issue.pct_change >= 0 ? "↑" : "↓"}${Math.abs(issue.pct_change)}%)`}
                    </span>
                  </Link>
                ))}
              </div>
              {data.emerging_issues.length > 0 && (
                <Link to="/issues" className="mt-3 inline-block text-sm text-primary-dark hover:underline">
                  View all recurring issues →
                </Link>
              )}
            </div>

            <div className="rounded-lg border border-border-warm bg-white p-4">
              <h2 className="mb-3 text-sm font-medium text-neutral-500">AI Performance</h2>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-neutral-500">Suggestion acceptance</span>
                  <span className="font-medium">{pct(data.ai_performance.acceptance_rate)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-neutral-500">Suggestion coverage</span>
                  <span className="font-medium">{pct(data.ai_performance.coverage_rate)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-neutral-500">Deflection rate (solved without an admin)</span>
                  <span className="font-medium">{pct(data.ai_performance.deflection_rate)}</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
