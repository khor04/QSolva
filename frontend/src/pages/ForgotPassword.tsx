import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { supabase } from "@/lib/supabase";

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    setLoading(false);
    if (error) setError(error.message);
    else setSent(true);
  }

  if (sent) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-cream">
        <div className="w-full max-w-sm rounded-lg border border-border-warm bg-white p-8 text-center shadow-sm">
          <p className="mb-4 text-sm text-neutral-600">
            If an account exists for that email, a password reset link has been sent. Check your inbox.
          </p>
          <Link to="/login" className="text-sm text-primary-dark underline">
            Back to sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-lg border border-border-warm bg-white p-8 shadow-sm">
        <h1 className="mb-2 text-xl font-semibold">Reset your password</h1>
        <p className="mb-6 text-sm text-neutral-500">
          Enter your account email and we'll send you a link to set a new password.
        </p>
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
        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Sending..." : "Send reset link"}
        </button>
        <p className="mt-4 text-center text-sm text-neutral-500">
          <Link to="/login" className="text-primary-dark underline">Back to sign in</Link>
        </p>
      </form>
    </div>
  );
}
