import { Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";

export function RoleRedirect() {
  const { profile } = useAuth();
  return <Navigate to={profile?.role === "admin" ? "/queue" : "/tickets"} replace />;
}
