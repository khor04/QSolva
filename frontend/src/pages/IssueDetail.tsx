import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { IssueClusterDetail, IssueSeverity } from "@/lib/types";
import { StatusBadge } from "@/components/Badge";

const SEVERITY_ICON: Record<IssueSeverity, string> = {
  emerging: "🔴",
  elevated: "🟠",
  watch: "🟡",
};

function lastNDays(n: number): string[] {
  const days: string[] = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    days.push(d.toISOString().slice(0, 10));
  }
  return days;
}

function Timeline({ timeline }: { timeline: IssueClusterDetail["timeline"] }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const countByDate = new Map(timeline.map((p) => [p.date, p.count]));
  const days = lastNDays(14);
  const counts = days.map((d) => countByDate.get(d) ?? 0);
  const max = Math.max(1, ...counts);

  return (
    <div className="flex items-end gap-1" style={{ height: 100 }}>
      {days.map((day, i) => (
        <div
          key={day}
          className="relative flex flex-1 flex-col items-center gap-1"
          onMouseEnter={() => setHovered(i)}
          onMouseLeave={() => setHovered((h) => (h === i ? null : h))}
        >
          {hovered === i && (
            <div className="absolute -top-7 z-10 rounded-md bg-neutral-800 px-2 py-1 text-xs font-medium text-white shadow-sm">
              {counts[i]} ticket{counts[i] === 1 ? "" : "s"}
            </div>
          )}
          <div
            className={`w-full rounded-t ${hovered === i ? "bg-primary" : "bg-primary/70"}`}
            style={{ height: `${Math.max(4, (counts[i] / max) * 80)}px` }}
          />
          <span className="text-[9px] text-neutral-400">{day.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}

export function IssueDetail() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draftQuestion, setDraftQuestion] = useState("");
  const [draftAnswer, setDraftAnswer] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["issues", id],
    queryFn: () => api.get<IssueClusterDetail>(`/issues/${id}`),
    enabled: !!id,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["issues", id] });
  const publish = useMutation({
    mutationFn: () => api.post(`/issues/${id}/article/publish`),
    onSuccess: invalidate,
  });
  const unpublish = useMutation({
    mutationFn: () => api.post(`/issues/${id}/article/unpublish`),
    onSuccess: invalidate,
  });
  const saveEdit = useMutation({
    mutationFn: (payload: { question: string; answer: string }) => api.patch(`/issues/${id}/article`, payload),
    onSuccess: () => {
      setEditing(false);
      invalidate();
    },
  });

  if (isLoading) return <p className="text-sm text-neutral-500">Loading...</p>;
  if (error || !data) return <p className="text-sm text-red-600">Failed to load issue.</p>;

  function startEditing() {
    setDraftQuestion(data!.article?.question ?? "");
    setDraftAnswer(data!.article?.answer ?? "");
    setEditing(true);
  }

  return (
    <div>
      <Link to="/issues" className="mb-4 inline-block text-sm text-primary-dark hover:underline">
        ← Recurring Issues
      </Link>

      <div className="mb-6 flex items-center gap-3">
        <h1 className="text-xl font-semibold">
          {SEVERITY_ICON[data.severity]} {data.label}
        </h1>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-border-warm bg-white p-4">
          <p className="text-2xl font-semibold">{data.tickets_this_week}</p>
          <p className="text-xs text-neutral-500">Tickets this week</p>
        </div>
        <div className="rounded-lg border border-border-warm bg-white p-4">
          <p className="text-2xl font-semibold">
            {data.pct_change != null ? `${data.pct_change >= 0 ? "↑" : "↓"} ${Math.abs(data.pct_change)}%` : "New"}
          </p>
          <p className="text-xs text-neutral-500">vs previous week</p>
        </div>
        <div className="rounded-lg border border-border-warm bg-white p-4">
          <p className="text-2xl font-semibold">{data.success_rate != null ? `${data.success_rate}%` : "—"}</p>
          <p className="text-xs text-neutral-500">Resolution success rate</p>
        </div>
        <div className="rounded-lg border border-border-warm bg-white p-4">
          <p className="text-2xl font-semibold capitalize">{data.category.replace("_", " ")}</p>
          <p className="text-xs text-neutral-500">Category</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-border-warm bg-white p-4">
          <h2 className="mb-3 text-sm font-medium text-neutral-500">Timeline (last 14 days)</h2>
          <Timeline timeline={data.timeline} />
        </div>

        <div className="rounded-lg border border-border-warm bg-white p-4">
          <h2 className="mb-3 text-sm font-medium text-neutral-500">Common Symptoms</h2>
          {data.symptoms && data.symptoms.length > 0 ? (
            <ul className="list-inside list-disc space-y-1 text-sm text-neutral-700">
              {data.symptoms.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-neutral-400">Not enough tickets yet to summarize common symptoms.</p>
          )}
        </div>

        <div className="rounded-lg border border-border-warm bg-white p-4">
          <h2 className="mb-3 text-sm font-medium text-neutral-500">Most Common Resolution</h2>
          {data.most_common_resolution ? (
            <>
              <p className="mb-3 whitespace-pre-wrap text-sm text-neutral-700">{data.most_common_resolution}</p>
              <div className="space-y-1 border-t border-primary-light/40 pt-3 text-xs text-neutral-500">
                {data.evidence.staff_confirmed > 0 && (
                  <p>✓ {data.evidence.staff_confirmed} staff-confirmed successful</p>
                )}
                {data.evidence.admin_resolved > 0 && (
                  <p>✓ {data.evidence.admin_resolved} admin-resolved</p>
                )}
                {data.evidence.unconfirmed > 0 && (
                  <p>⚠ {data.evidence.unconfirmed} closed without confirmation</p>
                )}
              </div>
            </>
          ) : (
            <p className="text-sm text-neutral-400">No resolution recorded yet for this issue.</p>
          )}
        </div>

        <div className="rounded-lg border border-border-warm bg-white p-4">
          <h2 className="mb-3 text-sm font-medium text-neutral-500">
            Related Tickets ({data.related_tickets.length})
          </h2>
          <div className="max-h-64 space-y-2 overflow-y-auto">
            {data.related_tickets.map((t) => (
              <Link
                key={t.id}
                to={`/tickets/${t.id}`}
                className="flex items-center justify-between gap-2 rounded-md border border-primary-light/40 px-3 py-2 text-sm hover:bg-primary-light/20"
              >
                <span className="truncate text-primary-dark">{t.title}</span>
                <StatusBadge status={t.status} />
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-lg border border-border-warm bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-neutral-500">Self-Service Article</h2>
          {data.article && (
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                data.article.status === "published"
                  ? "bg-green-100 text-green-700"
                  : "bg-amber-100 text-amber-700"
              }`}
            >
              {data.article.status === "published" ? "🟢 Published" : "🟡 Draft"}
            </span>
          )}
        </div>

        {!data.article && (
          <p className="text-sm text-neutral-400">
            No draft yet — an article is generated automatically once this issue has enough
            confirmed-solved tickets to write one from.
          </p>
        )}

        {data.article && !editing && (
          <div>
            <p className="mb-1 text-xs text-neutral-500">Q</p>
            <p className="mb-3 text-sm font-medium">{data.article.question}</p>
            <p className="mb-1 text-xs text-neutral-500">A</p>
            <p className="mb-4 whitespace-pre-wrap text-sm text-neutral-700">{data.article.answer}</p>
            {data.article.status === "published" && data.article.published_at && (
              <p className="mb-3 text-xs text-neutral-400">
                Published {new Date(data.article.published_at).toLocaleString()}
              </p>
            )}
            <div className="flex gap-2">
              <button
                onClick={startEditing}
                className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20"
              >
                Edit
              </button>
              {data.article.status === "draft" ? (
                <button
                  onClick={() => publish.mutate()}
                  disabled={publish.isPending}
                  className="rounded-md bg-primary px-3 py-1.5 text-sm text-white disabled:opacity-50"
                >
                  {publish.isPending ? "Publishing..." : "Publish"}
                </button>
              ) : (
                <button
                  onClick={() => unpublish.mutate()}
                  disabled={unpublish.isPending}
                  className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20 disabled:opacity-50"
                >
                  {unpublish.isPending ? "Unpublishing..." : "Unpublish"}
                </button>
              )}
            </div>
          </div>
        )}

        {editing && (
          <div>
            <label className="mb-1 block text-xs text-neutral-500">Question</label>
            <input
              value={draftQuestion}
              onChange={(e) => setDraftQuestion(e.target.value)}
              className="mb-3 w-full rounded-md border border-border-warm px-3 py-2 text-sm"
            />
            <label className="mb-1 block text-xs text-neutral-500">Answer</label>
            <textarea
              value={draftAnswer}
              onChange={(e) => setDraftAnswer(e.target.value)}
              rows={5}
              className="mb-3 w-full rounded-md border border-border-warm px-3 py-2 text-sm"
            />
            <div className="flex gap-2">
              <button
                onClick={() => saveEdit.mutate({ question: draftQuestion, answer: draftAnswer })}
                disabled={saveEdit.isPending || !draftQuestion.trim() || !draftAnswer.trim()}
                className="rounded-md bg-primary px-3 py-1.5 text-sm text-white disabled:opacity-50"
              >
                {saveEdit.isPending ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => setEditing(false)}
                disabled={saveEdit.isPending}
                className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
