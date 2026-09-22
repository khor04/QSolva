import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { TICKET_CATEGORIES, type IssueClusterDetail, type IssueClusterSummary, type IssueSeverity, type TicketCategory } from "@/lib/types";

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

function DeclareIncidentForm({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [label, setLabel] = useState("");
  const [category, setCategory] = useState<TicketCategory>("network");
  const [description, setDescription] = useState("");
  const [message, setMessage] = useState("");
  const [notifyAllStaff, setNotifyAllStaff] = useState(false);

  const create = useMutation({
    mutationFn: () =>
      api.post<IssueClusterDetail>("/issues", { label, category, description, message, notify_all_staff: notifyAllStaff }),
    onSuccess: (cluster) => {
      queryClient.invalidateQueries({ queryKey: ["issues"] });
      navigate(`/issues/${cluster.id}`);
    },
  });

  return (
    <div className="mb-6 rounded-lg border border-primary-light/50 bg-primary-light/10 p-4">
      <p className="mb-3 text-sm text-neutral-600">
        For a problem IT already knows about — from monitoring, an outage report, etc. — before any
        matching ticket has come in. Tickets that come in afterward will still auto-join this issue.
      </p>
      <label className="mb-1 block text-sm text-neutral-600 font-semibold">Label</label>
      <input
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="e.g. Email server outage"
        className="mb-3 w-full rounded-md border border-border-warm px-3 py-2 text-sm"
      />
      <label className="mb-1 block text-sm text-neutral-600 font-semibold">Category</label>
      <select
        value={category}
        onChange={(e) => setCategory(e.target.value as TicketCategory)}
        className="mb-3 w-full rounded-md border border-border-warm px-3 py-2 text-sm capitalize"
      >
        {TICKET_CATEGORIES.map((c) => (
          <option key={c} value={c} className="capitalize">
            {c.replace("_", " ")}
          </option>
        ))}
      </select>
      <label className="mb-1 block text-sm text-neutral-600 font-semibold">Problem description</label>
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="What's happening and what symptoms would a reporter see? Used to match incoming tickets to this issue."
        rows={2}
        className="mb-3 w-full rounded-md border border-border-warm px-3 py-2 text-sm"
      />
      <label className="mb-1 block text-sm text-neutral-600 font-semibold">Status message shown to affected staff</label>
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        placeholder="e.g. Email server is down. Investigating — updates to follow."
        rows={2}
        className="mb-3 w-full rounded-md border border-border-warm px-3 py-2 text-sm"
      />
      <label className="mb-3 flex items-start gap-2 text-sm text-neutral-700">
        <input
          type="checkbox"
          checked={notifyAllStaff}
          onChange={(e) => setNotifyAllStaff(e.target.checked)}
          className="mt-0.5"
        />
        <span>Notify all staff, not just those who've already filed a ticket.</span>
      </label>
      {create.isError && <p className="mb-2 text-sm text-red-600">Couldn't declare this incident. Please try again.</p>}
      <div className="flex gap-2">
        <button
          onClick={() => create.mutate()}
          disabled={create.isPending || !label.trim() || !description.trim() || !message.trim()}
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {create.isPending ? "Declaring..." : "Declare incident"}
        </button>
        <button
          onClick={onClose}
          disabled={create.isPending}
          className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20 disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export function IssuesList() {
  const [declaring, setDeclaring] = useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: ["issues"],
    queryFn: () => api.get<IssueClusterSummary[]>("/issues"),
  });

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Recurring Issues</h1>
        {!declaring && (
          <button
            onClick={() => setDeclaring(true)}
            className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20"
          >
            + Declare Incident
          </button>
        )}
      </div>
      <p className="mb-6 text-sm text-neutral-500">
        Tickets grouped by similarity, so systemic problems show up before they become a flood
        of individual tickets.
      </p>

      {declaring && <DeclareIncidentForm onClose={() => setDeclaring(false)} />}

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
