const statusColors: Record<string, string> = {
  open: "bg-blue-100 text-blue-700",
  in_progress: "bg-amber-100 text-amber-700",
  escalated: "bg-red-100 text-red-700",
  resolved: "bg-green-100 text-green-700",
  closed: "bg-neutral-200 text-neutral-600",
};

const priorityColors: Record<string, string> = {
  low: "bg-neutral-100 text-neutral-600",
  medium: "bg-amber-100 text-amber-700",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

function badgeClass(map: Record<string, string>, value: string) {
  return `rounded-full px-2 py-0.5 text-xs font-medium capitalize ${map[value] ?? "bg-neutral-100 text-neutral-600"}`;
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={badgeClass(statusColors, status)}>{status.replace("_", " ")}</span>;
}

export function PriorityBadge({ priority }: { priority: string }) {
  return <span className={badgeClass(priorityColors, priority)}>{priority}</span>;
}
