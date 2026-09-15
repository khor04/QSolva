import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { HelpCenterArticleDetail } from "@/lib/types";

export function HelpCenterArticle() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["help-center", id],
    queryFn: () => api.get<HelpCenterArticleDetail>(`/help-center/${id}`),
    enabled: !!id,
  });

  if (isLoading) return <p className="text-sm text-neutral-500">Loading...</p>;
  if (error || !data) return <p className="text-sm text-red-600">Article not found.</p>;

  return (
    <div>
      <Link to="/help-center" className="mb-4 inline-block text-sm text-primary-dark hover:underline">
        ← Help Center
      </Link>

      <p className="text-xs capitalize text-neutral-400">{data.category.replace("_", " ")}</p>
      <h1 className="mb-6 mt-1 text-xl font-semibold">{data.label}</h1>

      <div className="rounded-lg border border-border-warm bg-white p-6">
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-neutral-400">Q</p>
        <p className="mb-4 text-base font-medium">{data.question}</p>

        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-neutral-400">A</p>
        <p className="whitespace-pre-wrap text-sm text-neutral-700">{data.answer}</p>

        {data.total_feedback > 0 && (
          <p className="mt-4 text-sm text-neutral-500">
            ✓ Successfully resolved in {data.solved_count} of {data.total_feedback} similar cases
          </p>
        )}
      </div>

      <div className="mt-6 border-t border-primary-light/40 pt-4">
        <p className="mb-2 text-sm text-neutral-600">Still having trouble?</p>
        <Link
          to="/tickets/new"
          className="inline-block rounded-md bg-primary px-4 py-2 text-sm font-medium text-white"
        >
          Create a Ticket
        </Link>
      </div>
    </div>
  );
}
