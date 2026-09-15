import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/lib/supabase";
import { PasswordInput } from "@/components/PasswordInput";

export function Profile() {
  const { profile } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function handlePasswordSubmit(e: FormEvent) {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSaved(false);
    setPasswordLoading(true);
    const { error } = await supabase.auth.updateUser({ password });
    setPasswordLoading(false);
    if (error) setPasswordError(error.message);
    else {
      setPassword("");
      setPasswordSaved(true);
    }
  }

  const deleteAccount = useMutation({
    mutationFn: () => api.delete("/account"),
    onSuccess: async () => {
      await supabase.auth.signOut();
      navigate("/login", { replace: true });
    },
    onError: (err: Error) => setDeleteError(err.message),
  });

  return (
    <div className="mx-auto max-w-md space-y-6">
      <div>
        <h1 className="mb-2 text-xl font-semibold">Profile</h1>
        <div className="rounded-lg border border-border-warm bg-white p-4 text-sm">
          <p className="text-neutral-500">Name</p>
          <p className="mb-3 font-medium">{profile?.name}</p>
          <p className="text-neutral-500">Email</p>
          <p className="mb-3 font-medium">{profile?.email}</p>
          <p className="text-neutral-500">Role</p>
          <p className="font-medium capitalize">{profile?.role}</p>
        </div>
      </div>

      <div className="rounded-lg border border-border-warm bg-white p-4">
        <h2 className="mb-3 text-sm font-medium text-neutral-500">Change Password</h2>
        <form onSubmit={handlePasswordSubmit}>
          <div className="mb-3">
            <PasswordInput
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {passwordError && <p className="mb-3 text-sm text-red-600">{passwordError}</p>}
          {passwordSaved && <p className="mb-3 text-sm text-green-700">Password updated.</p>}
          <button
            type="submit"
            disabled={passwordLoading}
            className="rounded-md bg-primary px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {passwordLoading ? "Updating..." : "Update Password"}
          </button>
        </form>
      </div>

      <div className="rounded-lg border border-red-200 bg-white p-4">
        <h2 className="mb-2 text-sm font-medium text-red-700">Delete Account</h2>
        {!confirmingDelete ? (
          <>
            <p className="mb-3 text-sm text-neutral-500">
              Removes your name and email and signs you out permanently. Tickets you've submitted
              or handled stay on record for IT history — they'll just show "Deleted User" instead
              of your name. This can't be undone.
            </p>
            <button
              onClick={() => {
                setConfirmingDelete(true);
                setDeleteError(null);
              }}
              className="rounded-md border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50"
            >
              Delete My Account
            </button>
          </>
        ) : (
          <>
            <p className="mb-3 text-sm text-neutral-700">
              Are you sure? Your name/email will be permanently removed and you'll be signed out.
              This can't be undone.
            </p>
            {deleteError && <p className="mb-3 text-sm text-red-600">{deleteError}</p>}
            <div className="flex gap-2">
              <button
                onClick={() => deleteAccount.mutate()}
                disabled={deleteAccount.isPending}
                className="rounded-md bg-red-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
              >
                {deleteAccount.isPending ? "Deleting..." : "Yes, delete my account"}
              </button>
              <button
                onClick={() => setConfirmingDelete(false)}
                disabled={deleteAccount.isPending}
                className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20 disabled:opacity-50"
              >
                Cancel
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
