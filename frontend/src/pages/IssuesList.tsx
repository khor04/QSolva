import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { IssueClusterSummary, IssueSeverity } from "@/lib/types";

const SEVERITY_ICON: Record<IssueSeverity, string> = {
  emerging: "🔴",
  elevated: "🟠",
  watch: "🟡",
};

const SEVERITY_LABEL: Record<IssueSeverity, string> = {
  emerging: "Emerging Issue",
  elevated: "Elevated",
  watch: "Watching",
};

export function IssuesList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["issues"],
    queryFn: () => api.get<IssueClusterSummary[]>("/issues"),
  });

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold">Recurring Issues</h1>
      <p className="mb-6 text-sm text-neutral-500">
        Tickets grouped by similarity, so systemic problems show up before they become a flood
        of individual tickets.
      </p>

      {isLoading && <p className="text-sm text-neutral-500">Loading...</p>}
      {error && <p className="text-sm text-red-600">Failed to load recurring issues.</p>}
      {data && data.length === 0 && (
        <p className="text-sm text-neutral-500">
          No recurring issues yet — clusters appear once at least two similar tickets come in.
        </p>
      )}

      <div className="overflow-hidden rounded-lg border border-border-warm bg-white">
        {data?.map((issue, i) => (
          <Link
            key={issue.id}
            to={`/issues/${issue.id}`}
            className={`block px-5 py-4 hover:bg-primary-light/20 ${i > 0 ? "border-t border-primary-light/40" : ""}`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-neutral-400">
                  {SEVERITY_ICON[issue.severity]} {SEVERITY_LABEL[issue.severity]}
                </p>
                <p className="mt-1 text-base font-medium text-neutral-800">{issue.label}</p>
                <p className="mt-1 text-sm text-neutral-500">
                  {issue.tickets_this_week} ticket{issue.tickets_this_week === 1 ? "" : "s"} • Last 7 days
                  {issue.pct_change != null ? (
                    <span className={issue.pct_change >= 0 ? "text-red-600" : "text-green-600"}>
                      {" "}
                      {issue.pct_change >= 0 ? "↑" : "↓"} {Math.abs(issue.pct_change)}% vs previous week
                    </span>
                  ) : (
                    <span className="text-primary-dark"> • New this week</span>
                  )}
                </p>
                <p className="mt-1 text-xs capitalize text-neutral-400">{issue.category.replace("_", " ")}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                {issue.incident_status === "active" && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                    🔶 Active incident
                  </span>
                )}
                {issue.article_status && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      issue.article_status === "published"
                        ? "bg-green-100 text-green-700"
                        : "bg-amber-100 text-amber-700"
                    }`}
                  >
                    {issue.article_status === "published" ? "🟢 Published" : "🟡 Draft"}
                  </span>
                )}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
