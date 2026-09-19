import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";

export type Role = "staff" | "admin";

export interface Profile {
  id: string;
  name: string;
  email: string;
  role: Role;
}

interface AuthContextValue {
  session: Session | null;
  profile: Profile | null;
  loading: boolean;
  // Set when a valid Supabase session had no usable profile row, so the
  // login page can explain why the user was signed back out.
  profileError: string | null;
}

const AuthContext = createContext<AuthContextValue>({
  session: null,
  profile: null,
  loading: true,
  profileError: null,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  const userId = session?.user.id ?? null;

  useEffect(() => {
    if (!userId) {
      setProfile(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);

    supabase
      .from("users")
      .select("id, name, email, role")
      .eq("id", userId)
      .maybeSingle()
      .then(({ data, error }) => {
        if (cancelled) return;
        if (error || !data) {
          if (error) console.error("Failed to load profile", error);
          // A session with no profile can't use the app, and leaving it
          // signed in makes /login and ProtectedRoute redirect to each other
          // forever — so end the session and say why.
          setProfile(null);
          setProfileError(
            "Your account has no profile yet, so you were signed out. Please contact an administrator.",
          );
          supabase.auth.signOut();
        } else {
          setProfile(data as Profile);
          setProfileError(null);
        }
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // Deliberately keyed on user id, not the whole `session` object: Supabase
    // silently refreshes the access token in the background (same user, new
    // session reference), which would otherwise re-trigger this effect,
    // flip `loading` back to true, and (via ProtectedRoute) unmount the
    // entire page mid-interaction — wiping out whatever the user was typing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  return (
    <AuthContext.Provider value={{ session, profile, loading, profileError }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
