import { useState, type FormEvent } from "react";
import { Navigate, Link } from "react-router-dom";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/lib/auth";
import { PasswordInput } from "@/components/PasswordInput";

export function Register() {
  const { session } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  if (session) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    // Registration always creates a "staff" account. Admin accounts are
    // provisioned manually (seed script / DB), not self-service.
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { name } },
    });
    setLoading(false);
    if (error) setError(error.message);
    else setDone(true);
  }

  if (done) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-cream">
        <p className="text-sm text-neutral-600">
          Check your email to confirm your account, then <Link to="/login" className="underline">sign in</Link>.
        </p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-lg border border-border-warm bg-white p-8 shadow-sm">
        <h1 className="mb-6 text-xl font-semibold">Create your Qsolva account</h1>
        <div className="mb-4">
          <label className="mb-1 block text-sm text-neutral-600">Name</label>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border border-border-warm px-3 py-2 text-sm"
          />
        </div>
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
        <div className="mb-4">
          <label className="mb-1 block text-sm text-neutral-600">Password</label>
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
          {loading ? "Creating account..." : "Register"}
        </button>
        <p className="mt-4 text-center text-sm text-neutral-500">
          Already have an account? <Link to="/login" className="text-primary-dark underline">Sign in</Link>
        </p>
      </form>
    </div>
  );
}
