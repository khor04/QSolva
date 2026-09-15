import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { HelpCenterArticleSummary } from "@/lib/types";

export function HelpCenter() {
  const [search, setSearch] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["help-center"],
    queryFn: () => api.get<HelpCenterArticleSummary[]>("/help-center"),
  });

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (q === "") return data ?? [];
    return (data ?? []).filter(
      (a) => a.label.toLowerCase().includes(q) || a.question.toLowerCase().includes(q)
    );
  }, [data, search]);

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold">Help Center</h1>
      <p className="mb-6 text-sm text-neutral-500">
        Common problems and confirmed solutions from past IT support cases. Check here before
        submitting a ticket — you might not need to wait for an admin at all.
      </p>

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search for a problem..."
        className="mb-6 w-full max-w-md rounded-md border border-border-warm px-3 py-2 text-sm"
      />

      {isLoading && <p className="text-sm text-neutral-500">Loading...</p>}
      {error && <p className="text-sm text-red-600">Failed to load the Help Center.</p>}
      {data && data.length === 0 && (
        <p className="text-sm text-neutral-500">No published articles yet.</p>
      )}
      {data && data.length > 0 && filtered.length === 0 && (
        <p className="text-sm text-neutral-500">No articles match your search.</p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {filtered.map((article) => (
          <Link
            key={article.id}
            to={`/help-center/${article.id}`}
            className="rounded-lg border border-border-warm bg-white p-4 hover:bg-primary-light/20"
          >
            <p className="text-xs capitalize text-neutral-400">{article.category.replace("_", " ")}</p>
            <p className="mt-1 font-medium text-neutral-800">{article.label}</p>
            <p className="mt-1 text-sm text-neutral-600">{article.question}</p>
            {article.total_feedback > 0 && (
              <p className="mt-3 text-xs text-neutral-500">
                ✓ Based on {article.solved_count} of {article.total_feedback} successfully solved cases
              </p>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
