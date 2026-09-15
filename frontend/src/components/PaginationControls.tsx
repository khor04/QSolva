interface Props {
  page: number;
  totalPages: number;
  totalItems: number;
  onChange: (page: number) => void;
  itemLabel?: string;
}

export function PaginationControls({ page, totalPages, totalItems, onChange, itemLabel = "tickets" }: Props) {
  if (totalPages <= 1) return null;

  return (
    <div className="mt-3 flex items-center justify-between text-sm">
      <button
        onClick={() => onChange(Math.max(1, page - 1))}
        disabled={page === 1}
        className="rounded-md border border-border-warm px-3 py-1.5 hover:bg-primary-light/20 disabled:opacity-40"
      >
        Previous
      </button>
      <span className="text-neutral-500">
        Page {page} of {totalPages} &middot; {totalItems} {itemLabel}
      </span>
      <button
        onClick={() => onChange(Math.min(totalPages, page + 1))}
        disabled={page === totalPages}
        className="rounded-md border border-border-warm px-3 py-1.5 hover:bg-primary-light/20 disabled:opacity-40"
      >
        Next
      </button>
    </div>
  );
}
