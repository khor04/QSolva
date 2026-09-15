import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/lib/auth";
import { PasswordInput } from "@/components/PasswordInput";

export function ResetPassword() {
  const { session, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.updateUser({ password });
    if (error) {
      setLoading(false);
      setError(error.message);
      return;
    }
    await supabase.auth.signOut();
    navigate("/login", { replace: true });
  }

  if (authLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-cream text-sm text-neutral-500">Loading...</div>;
  }

  if (!session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-cream">
        <div className="w-full max-w-sm rounded-lg border border-border-warm bg-white p-8 text-center shadow-sm">
          <p className="mb-4 text-sm text-neutral-600">
            This password reset link is invalid or has expired.
          </p>
          <Link to="/forgot-password" className="text-sm text-primary-dark underline">
            Request a new one
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-lg border border-border-warm bg-white p-8 shadow-sm">
        <h1 className="mb-6 text-xl font-semibold">Set a new password</h1>
        <div className="mb-4">
          <label className="mb-1 block text-sm text-neutral-600">New password</label>
          <PasswordInput
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Updating..." : "Update password"}
        </button>
      </form>
    </div>
  );
}
