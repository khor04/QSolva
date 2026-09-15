import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AdminInviteCode } from "@/lib/types";

export function AdminAccess() {
  const [result, setResult] = useState<AdminInviteCode | null>(null);
  const [copied, setCopied] = useState(false);

  const generate = useMutation({
    mutationFn: () => api.post<AdminInviteCode>("/admin/invite-codes", { expires_in_days: 7, max_uses: 1 }),
    onSuccess: (data) => {
      setResult(data);
      setCopied(false);
    },
  });

  function handleCopy() {
    if (!result) return;
    navigator.clipboard.writeText(result.code);
    setCopied(true);
  }

  return (
    <div className="max-w-md">
      <h1 className="mb-2 text-xl font-semibold">Admin Access</h1>
      <p className="mb-6 text-sm text-neutral-500">
        Generate a one-time code so a new administrator can register. Anyone who has the code can
        register as an admin until it's used or expires — share it directly with the intended
        person, not over a public channel.
      </p>

      {!result && (
        <button
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {generate.isPending ? "Generating..." : "Generate Admin Invite Code"}
        </button>
      )}

      {result && (
        <div className="rounded-lg border border-border-warm bg-white p-4">
          <p className="mb-1 text-xs text-neutral-500">Admin Invite Code</p>
          <p className="mb-3 font-mono text-lg font-semibold tracking-wide">{result.code}</p>
          <p className="mb-4 text-sm text-neutral-500">
            {result.expires_at ? `Expires ${new Date(result.expires_at).toLocaleDateString()}` : "Never expires"}
            {" · Single use · "}
            <span className="font-medium text-amber-700">shown only once</span> — copy it now.
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleCopy}
              className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20"
            >
              {copied ? "Copied!" : "Copy Code"}
            </button>
            <button
              onClick={() => setResult(null)}
              className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
