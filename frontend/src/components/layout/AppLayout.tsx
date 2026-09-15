import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/lib/supabase";
import { NotificationBell } from "@/components/NotificationBell";

interface NavItem {
  to: string;
  label: string;
  end?: boolean;
}

const staffLinks: NavItem[] = [
  { to: "/tickets", label: "My Tickets", end: true },
  { to: "/tickets/new", label: "New Ticket" },
  { to: "/help-center", label: "Help Center" },
];

const adminLinks: NavItem[] = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/queue", label: "Ticket Queue" },
  { to: "/issues", label: "Recurring Issues" },
  { to: "/admin-access", label: "Admin Access" },
];

export function AppLayout() {
  const { profile } = useAuth();
  const links = profile?.role === "admin" ? adminLinks : staffLinks;

  return (
    <div className="min-h-screen bg-cream text-neutral-900">
      <header className="flex items-center justify-between border-b border-border-warm bg-white px-6 py-3">
        <div className="flex items-center gap-6">
          <img src="/q-mark.png" alt="Qsolva" className="h-10 w-auto" />          <nav className="flex gap-4 text-sm">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  isActive ? "font-medium text-primary-dark" : "text-neutral-500 hover:text-primary-dark"
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4 text-sm text-neutral-500">
          <NavLink to="/profile" className="hover:text-primary-dark hover:underline">
            {profile?.name} ({profile?.role})
          </NavLink>
          <NotificationBell />
          <button
            type="button"
            onClick={() => supabase.auth.signOut()}
            className="rounded-md border border-border-warm px-3 py-1 hover:bg-primary-light/30"
          >
            Sign out
          </button>

        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
