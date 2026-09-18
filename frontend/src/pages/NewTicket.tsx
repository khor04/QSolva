import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { uploadTicketAttachment } from "@/lib/storage";
import { AttachmentPicker } from "@/components/AttachmentPicker";
import type { ActiveIncidentMatch, Ticket, TicketCategory } from "@/lib/types";

const categories: TicketCategory[] = ["network", "hardware", "software", "email_account", "access", "other"];

export function NewTicket() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<TicketCategory>("network");
  const [attachments, setAttachments] = useState<File[]>([]);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const [createdTicketId, setCreatedTicketId] = useState<string | null>(null);
  const [incidentMatch, setIncidentMatch] = useState<ActiveIncidentMatch | null>(null);

  // Pre-submit check: does this look like a known, currently active
  // incident? Cheap on the backend (no AI call at all) when nothing's been
  // declared an incident, so it's fine to run on every submit attempt.
  const checkIncident = useMutation({
    mutationFn: () => api.post<ActiveIncidentMatch | null>("/tickets/check-active-incident", { title, description }),
  });

  const mutation = useMutation({
    mutationFn: async () => {
      const ticket = await api.post<Ticket>("/tickets", { title, description, category });

      const results = await Promise.allSettled(
        attachments.map(async (file) => {
          const fileUrl = await uploadTicketAttachment(ticket.id, file);
          await api.post(`/tickets/${ticket.id}/attachments`, { file_url: fileUrl });
        }),
      );
      const failed = results.filter((r) => r.status === "rejected").length;
      return { ticket, failed };
    },
    onSuccess: ({ ticket, failed }) => {
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      if (failed > 0) {
        // Don't navigate away immediately here: the ticket detail page
        // would unmount this component before the user could ever read
        // the error, making attachment failures silently invisible.
        setAttachmentError(
          `${failed} of ${attachments.length} attachment(s) failed to upload. The ticket was created without ${failed === 1 ? "it" : "them"}.`,
        );
        setCreatedTicketId(ticket.id);
      } else {
        navigate(`/tickets/${ticket.id}`);
      }
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setAttachmentError(null);
    checkIncident.mutate(undefined, {
      onSuccess: (match) => {
        if (match) {
          setIncidentMatch(match);
        } else {
          mutation.mutate();
        }
      },
      // If the check itself fails (e.g. network hiccup), don't block
      // submission on it — worst case, the reporter just doesn't get the
      // heads-up and files a ticket that later turns out to be a duplicate.
      onError: () => mutation.mutate(),
    });
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="mb-2 text-xl font-semibold">Create New Ticket</h1>
      <p className="mb-6 text-sm text-neutral-500">
        Common problems already have confirmed fixes — check the{" "}
        <Link to="/help-center" className="text-primary-dark underline">
          Help Center
        </Link>{" "}
        first, you might not need to submit a ticket at all.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-border-warm bg-white p-6">
        <div>
          <label className="mb-1 block text-sm text-neutral-600">Title</label>
          <input
            required
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setIncidentMatch(null);
            }}
            placeholder="VPN connection keeps timing out"
            className="w-full rounded-md border border-border-warm px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm text-neutral-600">Description</label>
          <textarea
            required
            rows={5}
            value={description}
            onChange={(e) => {
              setDescription(e.target.value);
              setIncidentMatch(null);
            }}
            placeholder="Describe what's happening, when it started, and what you've already tried..."
            className="w-full rounded-md border border-border-warm px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm text-neutral-600">Category</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as TicketCategory)}
            className="w-full rounded-md border border-border-warm px-3 py-2 text-sm capitalize"
          >
            {categories.map((c) => (
              <option key={c} value={c} className="capitalize">
                {c.replace("_", " ")}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm text-neutral-600">Attachment</label>
          <AttachmentPicker files={attachments} onChange={setAttachments} />
        </div>
        {incidentMatch && (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            <p className="mb-1 font-medium">🔶 This looks like a known active issue: {incidentMatch.label}</p>
            {incidentMatch.message && <p className="mb-3 whitespace-pre-wrap">{incidentMatch.message}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => mutation.mutate()}
                disabled={mutation.isPending}
                className="rounded-md bg-primary px-3 py-1.5 text-sm text-white disabled:opacity-50"
              >
                {mutation.isPending ? "Submitting..." : "I'm affected too — notify me"}
              </button>
              <button
                type="button"
                onClick={() => setIncidentMatch(null)}
                disabled={mutation.isPending}
                className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20 disabled:opacity-50"
              >
                This is different — keep editing
              </button>
            </div>
          </div>
        )}
        {attachmentError && (
          <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
            <p className="mb-2">{attachmentError}</p>
            {createdTicketId && (
              <Link to={`/tickets/${createdTicketId}`} className="font-medium underline">
                Continue to ticket
              </Link>
            )}
          </div>
        )}
        {mutation.isError && <p className="text-sm text-red-600">Failed to submit ticket.</p>}
        {!incidentMatch && (
          <button
            type="submit"
            disabled={checkIncident.isPending || mutation.isPending || createdTicketId !== null}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {checkIncident.isPending ? "Checking..." : mutation.isPending ? "Submitting..." : "Submit Ticket"}
          </button>
        )}
      </form>
    </div>
  );
}
