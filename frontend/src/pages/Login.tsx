import { useState, type FormEvent } from "react";
import { Navigate, Link } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/lib/auth";
import { PasswordInput } from "@/components/PasswordInput";

export function Login() {
  const { session, profile, profileError } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Needs the profile too: ProtectedRoute bounces a profile-less session back
  // here, so redirecting on the session alone would loop.
  if (session && profile) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) setError(error.message);
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-lg border border-border-warm bg-white p-8 shadow-sm">
        <h1 className="mb-6 text-xl font-semibold">Sign in to Qsolva</h1>
        <div className="mb-4">
          <label className="mb-1 block text-sm text-neutral-600">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-border-warm px-3 py-2 text-sm"
          />
        </div>
        <div className="mb-2">
          <label className="mb-1 block text-sm text-neutral-600">Password</label>
          <PasswordInput
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <p className="mb-4 text-right text-sm">
          <Link to="/forgot-password" className="text-primary-dark underline">Forgot password?</Link>
        </p>
        {(error ?? profileError) && <p className="mb-4 text-sm text-red-600">{error ?? profileError}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Signing in..." : "Sign in"}
        </button>
        <p className="mt-4 text-center text-sm text-neutral-500">
          No account? <Link to="/register" className="text-primary-dark underline">Register</Link>
        </p>
      </form>
    </div>
  );
}
