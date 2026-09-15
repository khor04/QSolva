import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth, type Role } from "@/lib/auth";

export function ProtectedRoute({
  children,
  allow,
}: {
  children: ReactNode;
  allow?: Role[];
}) {
  const { session, profile, loading } = useAuth();

  if (loading) {
    return <div className="flex h-screen items-center justify-center text-sm text-neutral-500">Loading...</div>;
  }

  if (!session || !profile) {
    return <Navigate to="/login" replace />;
  }

  if (allow && !allow.includes(profile.role)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
