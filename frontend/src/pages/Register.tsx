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
  const [accountType, setAccountType] = useState<"staff" | "admin">("staff");
  const [adminCode, setAdminCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  if (session) return <Navigate to="/" replace />;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    // The role is never trusted from the client: a DB trigger
    // (handle_new_user, see backend/alembic/versions/0008_admin_invite_codes.py)
    // only grants "admin" if admin_code atomically claims an unused, unexpired
    // invite code — otherwise the whole signup is rejected server-side.
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          name,
          requested_role: accountType,
          ...(accountType === "admin" ? { admin_code: adminCode } : {}),
        },
      },
    });
    setLoading(false);
    if (error) setError(error.message);
    else setDone(true);
  }

  if (done) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-cream">
        <div className="w-full max-w-sm rounded-lg border border-border-warm bg-white p-8 shadow-sm">
          <h1 className="mb-3 text-xl font-semibold">Check your email</h1>
          <p className="mb-4 text-sm text-neutral-600">
            If an account can be created with this email address, we'll send you a confirmation
            link.
          </p>
          <p className="mb-2 text-sm font-medium text-neutral-700">Didn't receive an email?</p>
          <ul className="mb-4 list-disc space-y-1 pl-5 text-sm text-neutral-600">
            <li>Check your spam folder</li>
            <li>Make sure the email address is correct</li>
            <li>
              Already have an account? <Link to="/login" className="text-primary-dark underline">Sign in</Link> instead
            </li>
            <li>
              Forgot your password?{" "}
              <Link to="/forgot-password" className="text-primary-dark underline">Reset it</Link>
            </li>
          </ul>
          <p className="text-sm text-neutral-500">
            Received the email? <Link to="/login" className="text-primary-dark underline">Sign in</Link>
          </p>
        </div>
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
        <div className="mb-4">
          <label className="mb-1 block text-sm text-neutral-600">Account Type</label>
          <div className="flex gap-4 text-sm text-neutral-700">
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="account-type"
                checked={accountType === "staff"}
                onChange={() => setAccountType("staff")}
              />
              Staff
            </label>
            <label className="flex items-center gap-1.5">
              <input
                type="radio"
                name="account-type"
                checked={accountType === "admin"}
                onChange={() => setAccountType("admin")}
              />
              Admin
            </label>
          </div>
        </div>
        {accountType === "admin" && (
          <div className="mb-4">
            <label className="mb-1 block text-sm text-neutral-600">Admin Invite Code</label>
            <input
              required
              value={adminCode}
              onChange={(e) => setAdminCode(e.target.value)}
              placeholder="Provided by the system administrator"
              className="w-full rounded-md border border-border-warm px-3 py-2 text-sm"
            />
          </div>
        )}
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
