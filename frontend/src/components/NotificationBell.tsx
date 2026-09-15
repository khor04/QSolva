import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth, type Role } from "@/lib/auth";
import type { Notification, NotificationType } from "@/lib/types";

const MESSAGES: Record<NotificationType, (title: string, viewerRole?: Role) => string> = {
  ticket_updated: (t) => `Your ticket "${t}" was updated.`,
  ticket_replied: (t) => `Admin replied on "${t}".`,
  ticket_resolved: (t) => `"${t}" was confirmed resolved.`,
  resolution_confirm_needed: (t) => `"${t}" was marked resolved — please confirm.`,
  new_critical_ticket: (t) => `New critical ticket: "${t}".`,
  staff_replied: (t) => `Staff replied on "${t}".`,
  suggestion_failed: (t) => `AI couldn't analyze "${t}".`,
  sla_risk: (t) => `"${t}" is at risk of breaching its SLA.`,
  ticket_escalated: (t, viewerRole) =>
    viewerRole === "admin"
      ? `🔴 Ticket escalated — "${t}" needs another admin's attention.`
      : `Your ticket "${t}" has been escalated to another administrator for further investigation.`,
};

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { profile } = useAuth();

  const { data } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<Notification[]>("/notifications"),
    refetchInterval: 20_000,
  });

  const notifications = data ?? [];
  const unreadCount = notifications.filter((n) => !n.is_read).length;

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["notifications"] });
  const markRead = useMutation({
    mutationFn: (id: string) => api.post(`/notifications/${id}/read`),
    onSuccess: invalidate,
  });
  const markAllRead = useMutation({
    mutationFn: () => api.post(`/notifications/read-all`),
    onSuccess: invalidate,
  });

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  function handleSelect(n: Notification) {
    if (!n.is_read) markRead.mutate(n.id);
    setOpen(false);
    if (n.ticket_id) navigate(`/tickets/${n.ticket_id}`);
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="relative rounded-md border border-border-warm p-1.5 hover:bg-primary-light/30"
        aria-label="Notifications"
      >
        <svg className="h-5 w-5 text-neutral-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 10-12 0v3.2a2 2 0 01-.6 1.4L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-medium text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-10 mt-2 w-80 rounded-lg border border-border-warm bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-border-warm px-3 py-2">
            <span className="text-sm font-medium">Notifications</span>
            {unreadCount > 0 && (
              <button
                onClick={() => markAllRead.mutate()}
                className="text-xs text-primary-dark hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-80 overflow-y-auto">
            {notifications.length === 0 && (
              <p className="px-3 py-4 text-sm text-neutral-400">No notifications yet.</p>
            )}
            {notifications.map((n) => (
              <button
                key={n.id}
                onClick={() => handleSelect(n)}
                className={`block w-full border-b border-primary-light/40 px-3 py-2 text-left text-sm last:border-0 hover:bg-primary-light/20 ${
                  n.is_read ? "text-neutral-500" : "font-medium text-neutral-800"
                }`}
              >
                <div className="flex items-start gap-2">
                  {!n.is_read && <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />}
                  <div className={n.is_read ? "ml-3.5" : ""}>
                    <p>{MESSAGES[n.type](n.ticket_title ?? "a ticket", profile?.role)}</p>
                    <p className="mt-0.5 text-xs text-neutral-400">{timeAgo(n.created_at)}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
