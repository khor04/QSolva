import { useState } from "react";
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
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-cream text-neutral-900">
      <header className="border-b border-border-warm bg-white px-4 py-3 sm:px-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <img src="/q-mark.png" alt="Qsolva" className="h-10 w-auto" />
            <nav className="hidden gap-4 text-sm md:flex">
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
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-4 text-sm text-neutral-500 md:flex">
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
            <div className="flex items-center gap-2 md:hidden">
              <NotificationBell />
              <button
                type="button"
                onClick={() => setMenuOpen((v) => !v)}
                aria-label="Toggle menu"
                aria-expanded={menuOpen}
                className="rounded-md border border-border-warm p-1.5 hover:bg-primary-light/30"
              >
                <svg className="h-5 w-5 text-neutral-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  {menuOpen ? (
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  ) : (
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                  )}
                </svg>
              </button>
            </div>
          </div>
        </div>

        {menuOpen && (
          <div className="mt-3 border-t border-border-warm pt-3 md:hidden">
            <nav className="flex flex-col gap-1 text-sm">
              {links.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.end}
                  onClick={() => setMenuOpen(false)}
                  className={({ isActive }) =>
                    `rounded-md px-2 py-2 ${isActive ? "font-medium text-primary-dark" : "text-neutral-500 hover:text-primary-dark"}`
                  }
                >
                  {link.label}
                </NavLink>
              ))}
            </nav>
            <div className="mt-2 flex items-center justify-between border-t border-border-warm px-2 pt-3 text-sm text-neutral-500">
              <NavLink to="/profile" onClick={() => setMenuOpen(false)} className="hover:text-primary-dark hover:underline">
                {profile?.name} ({profile?.role})
              </NavLink>
              <button
                type="button"
                onClick={() => supabase.auth.signOut()}
                className="rounded-md border border-border-warm px-3 py-1 hover:bg-primary-light/30"
              >
                Sign out
              </button>
            </div>
          </div>
        )}
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  );
}
