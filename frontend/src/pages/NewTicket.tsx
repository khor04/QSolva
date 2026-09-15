import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { uploadTicketAttachment } from "@/lib/storage";
import { AttachmentPicker } from "@/components/AttachmentPicker";
import type { Ticket, TicketCategory } from "@/lib/types";

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
    mutation.mutate();
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
            onChange={(e) => setTitle(e.target.value)}
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
            onChange={(e) => setDescription(e.target.value)}
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
        <button
          type="submit"
          disabled={mutation.isPending || createdTicketId !== null}
          className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {mutation.isPending ? "Submitting..." : "Submit Ticket"}
        </button>
      </form>
    </div>
  );
}
