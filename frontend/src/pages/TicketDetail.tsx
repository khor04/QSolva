import { useRef, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { FeedbackOutcome, TicketDetailResponse, TicketPriority, TicketStatus } from "@/lib/types";

const NEGATIVE_OUTCOMES: { value: FeedbackOutcome; label: string }[] = [
  { value: "partially_solved", label: "Partially solved" },
  { value: "did_not_solve", label: "Didn't solve the problem" },
  { value: "wrong_recommendation", label: "Wrong recommendation" },
  { value: "other", label: "Other" },
];

function NegativeFeedbackForm({
  isPending,
  onSubmit,
  onCancel,
}: {
  isPending: boolean;
  onSubmit: (outcome: FeedbackOutcome, comment: string) => void;
  onCancel: () => void;
}) {
  const [outcome, setOutcome] = useState<FeedbackOutcome>("did_not_solve");
  const [comment, setComment] = useState("");

  return (
    <div className="rounded-md border border-border-warm bg-cream/60 p-3">
      <p className="mb-2 text-sm font-medium">What happened?</p>
      <div className="mb-3 space-y-1.5">
        {NEGATIVE_OUTCOMES.map((opt) => (
          <label key={opt.value} className="flex items-center gap-2 text-sm text-neutral-700">
            <input
              type="radio"
              name="feedback-outcome"
              checked={outcome === opt.value}
              onChange={() => setOutcome(opt.value)}
            />
            {opt.label}
          </label>
        ))}
      </div>
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Anything else to add? (optional)"
        rows={2}
        className="mb-3 w-full rounded-md border border-border-warm px-3 py-2 text-sm"
      />
      <div className="flex gap-2">
        <button
          onClick={() => onSubmit(outcome, comment)}
          disabled={isPending}
          className="rounded-md bg-primary px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {isPending ? "Submitting..." : "Submit Feedback"}
        </button>
        <button
          onClick={onCancel}
          disabled={isPending}
          className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20 disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

const PRIORITY_MESSAGES: Record<TicketPriority, string> = {
  critical: "This is treated as a critical issue affecting business operations.",
  high: "Your issue may significantly affect your work.",
  medium: "This will be handled as a standard priority issue.",
  low: "This is a minor issue and will be handled in due course.",
};

const PRIORITY_OPTIONS: TicketPriority[] = ["low", "medium", "high", "critical"];
import { StatusBadge, PriorityBadge } from "@/components/Badge";

export function TicketDetail() {
  const { id } = useParams<{ id: string }>();
  const { profile } = useAuth();
  const isAdmin = profile?.role === "admin";
  const queryClient = useQueryClient();
  const [reply, setReply] = useState("");
  const [confirmingSolved, setConfirmingSolved] = useState(false);
  const [confirmingEscalate, setConfirmingEscalate] = useState(false);
  const [confirmingSelfResolve, setConfirmingSelfResolve] = useState(false);
  const [showResolvedFeedbackForm, setShowResolvedFeedbackForm] = useState(false);
  const [showSuggestionFeedbackForm, setShowSuggestionFeedbackForm] = useState(false);
  const pendingSinceRef = useRef<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["tickets", id],
    queryFn: () => api.get<TicketDetailResponse>(`/tickets/${id}`),
    enabled: !!id,
    // Poll while either AI stage is still "pending" so the "analyzing"
    // state resolves on its own — including after a manual retry, not just
    // right after creation. Give up after 90s of continuous pending in case
    // the background task itself crashed, rather than polling forever.
    refetchInterval: (query) => {
      const t = query.state.data?.ticket;
      const pending = !!t && (t.ai_priority_status === "pending" || t.ai_rag_status === "pending");
      if (!pending) {
        pendingSinceRef.current = null;
        return false;
      }
      if (pendingSinceRef.current == null) pendingSinceRef.current = Date.now();
      return Date.now() - pendingSinceRef.current < 90_000 ? 3000 : false;
    },
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["tickets", id] });

  const sendMessage = useMutation({
    mutationFn: () => api.post(`/tickets/${id}/messages`, { body: reply }),
    onSuccess: () => {
      setReply("");
      invalidate();
    },
  });

  const claim = useMutation({ mutationFn: () => api.post(`/tickets/${id}/claim`), onSuccess: invalidate });
  const unassign = useMutation({ mutationFn: () => api.post(`/tickets/${id}/unassign`), onSuccess: invalidate });
  const escalate = useMutation({
    mutationFn: () => api.post(`/tickets/${id}/escalate`),
    onSuccess: () => {
      setConfirmingEscalate(false);
      invalidate();
    },
  });
  const setStatus = useMutation({
    mutationFn: (status: TicketStatus) => api.patch(`/tickets/${id}`, { status }),
    onSuccess: invalidate,
  });
  const setPriority = useMutation({
    mutationFn: (priority: TicketPriority) => api.patch(`/tickets/${id}`, { priority }),
    onSuccess: invalidate,
  });
  const retryEnrichment = useMutation({
    mutationFn: () => api.post(`/tickets/${id}/retry-enrichment`),
    onSuccess: invalidate,
  });
  const sendFeedback = useMutation({
    mutationFn: (payload: { outcome: FeedbackOutcome; comment?: string }) =>
      api.post(`/tickets/${id}/feedback`, payload),
    onSuccess: () => {
      setConfirmingSolved(false);
      setConfirmingSelfResolve(false);
      setShowResolvedFeedbackForm(false);
      setShowSuggestionFeedbackForm(false);
      invalidate();
    },
  });

  if (isLoading) return <p className="text-sm text-neutral-500">Loading...</p>;
  if (error || !data) return <p className="text-sm text-red-600">Failed to load ticket.</p>;

  const { ticket, messages, suggestion } = data;
  const isTicketDone = ticket.status === "resolved" || ticket.status === "closed";
  const analyzing = ticket.ai_priority_status === "pending" || ticket.ai_rag_status === "pending";
  const aiFailed = ticket.ai_priority_status === "failed" || ticket.ai_rag_status === "failed";

  function handleReply(e: FormEvent) {
    e.preventDefault();
    if (reply.trim()) sendMessage.mutate();
  }

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        <h1 className="text-xl font-semibold">{ticket.title}</h1>
        <PriorityBadge priority={ticket.priority} />
        <StatusBadge status={ticket.status} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.3fr_1fr]">
        {/* Conversation */}
        <div className="rounded-lg border border-border-warm bg-white p-4">
          <h2 className="mb-3 text-sm font-medium text-neutral-500">Conversation</h2>
          <p className="mb-4 whitespace-pre-wrap rounded-md bg-cream p-3 text-sm">{ticket.description}</p>
          {data.attachments.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-2">
              {data.attachments.map((a) => (
                <a key={a.id} href={a.file_url} target="_blank" rel="noreferrer">
                  <img
                    src={a.file_url}
                    alt="Attachment"
                    className="h-20 w-20 rounded-md border border-border-warm object-cover"
                  />
                </a>
              ))}
            </div>
          )}
          <div className="mb-4 space-y-3">
            {messages.map((m) => (
              <div key={m.id} className="rounded-md border border-primary-light/40 p-3 text-sm">
                <p className="mb-1 text-xs text-neutral-400">{new Date(m.created_at).toLocaleString()}</p>
                <p className="whitespace-pre-wrap">{m.body}</p>
              </div>
            ))}
            {messages.length === 0 && <p className="text-sm text-neutral-400">No replies yet.</p>}
          </div>
          <form onSubmit={handleReply} className="flex gap-2">
            <input
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              placeholder="Write a reply..."
              className="flex-1 rounded-md border border-border-warm px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={sendMessage.isPending}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Reply
            </button>
          </form>

          {isAdmin && !isTicketDone && (
            <div className="mt-4 border-t border-primary-light/40 pt-4">
              {ticket.status === "escalated" && !ticket.assigned_admin_id && (
                <p className="mb-3 text-sm text-neutral-500">
                  Escalated by{" "}
                  {ticket.escalated_by_admin_id === profile?.id
                    ? "you"
                    : ticket.escalated_by_admin_id
                      ? ticket.escalated_by_admin_id.slice(0, 8)
                      : "another admin"}{" "}
                  — back in the queue for another admin to take over.
                </p>
              )}

              {!confirmingEscalate && (
                <div className="flex flex-wrap items-center gap-2">
                  {!ticket.assigned_admin_id && (
                    <button onClick={() => claim.mutate()} className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20">
                      Claim
                    </button>
                  )}
                  {ticket.assigned_admin_id && (
                    <button onClick={() => unassign.mutate()} className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20">
                      Unassign
                    </button>
                  )}
                  {ticket.assigned_admin_id === profile?.id && (
                    <button onClick={() => setConfirmingEscalate(true)} className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20">
                      Escalate
                    </button>
                  )}
                  <button onClick={() => setStatus.mutate("resolved")} className="rounded-md bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700">
                    Mark Resolved
                  </button>
                </div>
              )}

              {confirmingEscalate && (
                <div className="rounded-md border border-primary-light/50 bg-primary-light/10 p-3">
                  <p className="mb-3 text-sm">
                    Escalate this ticket? This will release it back to the admin queue so another
                    administrator can take over.
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => escalate.mutate()}
                      disabled={escalate.isPending}
                      className="rounded-md bg-primary px-3 py-1.5 text-sm text-white disabled:opacity-50"
                    >
                      {escalate.isPending ? "Escalating..." : "Escalate Ticket"}
                    </button>
                    <button
                      onClick={() => setConfirmingEscalate(false)}
                      disabled={escalate.isPending}
                      className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {isAdmin && isTicketDone && (
            <div className="mt-4 border-t border-primary-light/40 pt-4">
              <p className="text-sm text-neutral-500">
                {ticket.status === "closed"
                  ? "This ticket is closed — the staff member confirmed the issue was resolved."
                  : "Marked resolved — waiting for the staff member to confirm it worked."}
              </p>
            </div>
          )}

          {!isAdmin && ticket.status === "resolved" && (
            <div className="mt-4 border-t border-primary-light/40 pt-4">
              {!showResolvedFeedbackForm ? (
                <>
                  <p className="mb-2 text-sm font-medium">Did this resolve your issue?</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => sendFeedback.mutate({ outcome: "solved" })}
                      className="rounded-md bg-green-600 px-3 py-1.5 text-sm text-white"
                    >
                      Yes, solved
                    </button>
                    <button
                      onClick={() => setShowResolvedFeedbackForm(true)}
                      className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20"
                    >
                      Still not working
                    </button>
                  </div>
                </>
              ) : (
                <NegativeFeedbackForm
                  isPending={sendFeedback.isPending}
                  onSubmit={(outcome, comment) => sendFeedback.mutate({ outcome, comment: comment || undefined })}
                  onCancel={() => setShowResolvedFeedbackForm(false)}
                />
              )}
            </div>
          )}

          {!isAdmin && !isTicketDone && ticket.status !== "resolved" && (
            <div className="mt-4 border-t border-primary-light/40 pt-4">
              {!confirmingSelfResolve ? (
                <button
                  onClick={() => setConfirmingSelfResolve(true)}
                  className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20"
                >
                  Mark as Resolved
                </button>
              ) : (
                <div className="rounded-md border border-primary-light/50 bg-primary-light/10 p-3">
                  <p className="mb-3 text-sm">
                    Confirm your issue is resolved? This will close the ticket.
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => sendFeedback.mutate({ outcome: "solved" })}
                      disabled={sendFeedback.isPending}
                      className="rounded-md bg-primary px-3 py-1.5 text-sm text-white disabled:opacity-50"
                    >
                      {sendFeedback.isPending ? "Closing..." : "Yes, close ticket"}
                    </button>
                    <button
                      onClick={() => setConfirmingSelfResolve(false)}
                      disabled={sendFeedback.isPending}
                      className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20 disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="space-y-6">
          {/* AI Triage */}
          <div className="rounded-lg border border-border-warm bg-white p-4">
            <h2 className="mb-3 text-sm font-medium text-neutral-500">AI Triage</h2>

            {!isAdmin && (
              <div className="flex items-center gap-2">
                <PriorityBadge priority={ticket.priority} />
                <p className="text-sm text-neutral-600">{PRIORITY_MESSAGES[ticket.priority]}</p>
              </div>
            )}

            {isAdmin && (
              <div>
                {ticket.ai_priority_status === "failed" && (
                  <div className="mb-2 flex items-center gap-2">
                    <p className="text-xs text-amber-700">
                      ⚠️ AI priority classification failed — showing default priority.
                    </p>
                    {ticket.ai_rag_status !== "failed" && (
                      <button
                        onClick={() => retryEnrichment.mutate()}
                        disabled={retryEnrichment.isPending}
                        className="text-xs font-medium text-primary-dark hover:underline disabled:opacity-50"
                      >
                        {retryEnrichment.isPending ? "Retrying..." : "Retry"}
                      </button>
                    )}
                  </div>
                )}
                <div className="mb-3 flex items-center gap-2">
                  <PriorityBadge priority={ticket.priority} />
                  {ticket.priority_confidence != null && (
                    <span className="text-sm text-neutral-500">
                      {Math.round(ticket.priority_confidence * 100)}% confidence
                    </span>
                  )}
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
                      ticket.priority_source === "manual"
                        ? "bg-primary-light/40 text-primary-dark"
                        : "bg-neutral-100 text-neutral-500"
                    }`}
                  >
                    {ticket.priority_source}
                  </span>
                </div>
                {ticket.priority_reason && (
                  <p className="mb-3 text-sm text-neutral-600">{ticket.priority_reason}</p>
                )}
                <label className="mb-1 block text-xs text-neutral-500">Override priority</label>
                <select
                  value={ticket.priority}
                  onChange={(e) => setPriority.mutate(e.target.value as TicketPriority)}
                  className="rounded-md border border-border-warm px-2 py-1 text-sm capitalize"
                >
                  {PRIORITY_OPTIONS.map((p) => (
                    <option key={p} value={p} className="capitalize">
                      {p}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* AI Resolution Assistant */}
          <div className="rounded-lg border border-border-warm bg-white p-4">
            {isAdmin && <h2 className="mb-3 text-sm font-medium text-neutral-500">AI Resolution Assistant</h2>}

            {analyzing && (
              <div className="flex items-center gap-2 text-sm text-neutral-400">
                <svg className="h-4 w-4 animate-spin text-primary" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                <span>
                  Analyzing similar cases
                  <span className="inline-flex w-4 justify-start">
                    <span className="animate-bounce [animation-delay:-0.3s]">.</span>
                    <span className="animate-bounce [animation-delay:-0.15s]">.</span>
                    <span className="animate-bounce">.</span>
                  </span>
                </span>
              </div>
            )}

            {!analyzing && ticket.ai_rag_status === "failed" && (
              <div>
                <p className="mb-1 text-sm font-medium text-amber-700">⚠️ AI analysis unavailable</p>
                <p className="mb-3 text-sm text-neutral-500">
                  QSolva couldn't find or generate a troubleshooting suggestion for this ticket.
                  It's been sent to IT Support in the meantime.
                </p>
                {isAdmin && (
                  <button
                    onClick={() => retryEnrichment.mutate()}
                    disabled={retryEnrichment.isPending}
                    className="rounded-md bg-primary px-3 py-1.5 text-sm text-white disabled:opacity-50"
                  >
                    {retryEnrichment.isPending ? "Retrying..." : "Retry AI Analysis"}
                  </button>
                )}
              </div>
            )}

            {!analyzing && ticket.ai_rag_status !== "failed" && !suggestion && (
              <p className="text-sm text-neutral-400">
                We couldn't find a similar resolved case for this yet. It's been sent to IT Support.
              </p>
            )}

            {suggestion && !isAdmin && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-neutral-700">💡 Try This First</h3>
                <p className="mb-3 text-sm text-neutral-500">
                  We found a similar issue that's been resolved before:
                </p>
                <div className="mb-3 whitespace-pre-wrap rounded-md border border-primary-light/40 bg-primary-light/10 p-3 text-sm">
                  {suggestion.resolution_text}
                </div>
                {suggestion.evidence.length > 0 && (
                  <p className="mb-4 text-xs text-neutral-500">
                    ✓ Based on {suggestion.evidence.length} similar resolved{" "}
                    {suggestion.evidence.length === 1 ? "case" : "cases"}
                  </p>
                )}

                {suggestion.state === "available" &&
                  !isTicketDone &&
                  !confirmingSolved &&
                  !showSuggestionFeedbackForm && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => setConfirmingSolved(true)}
                        className="rounded-md bg-primary px-3 py-1.5 text-sm text-white"
                      >
                        This worked
                      </button>
                      <button
                        onClick={() => setShowSuggestionFeedbackForm(true)}
                        className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20"
                      >
                        Still having trouble
                      </button>
                    </div>
                  )}

                {showSuggestionFeedbackForm && (
                  <NegativeFeedbackForm
                    isPending={sendFeedback.isPending}
                    onSubmit={(outcome, comment) => sendFeedback.mutate({ outcome, comment: comment || undefined })}
                    onCancel={() => setShowSuggestionFeedbackForm(false)}
                  />
                )}

                {confirmingSolved && (
                  <div className="rounded-md border border-primary-light/50 bg-primary-light/10 p-3">
                    <p className="mb-3 text-sm">
                      Confirm this solved your issue? This ticket will be closed.
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={() => sendFeedback.mutate({ outcome: "solved" })}
                        disabled={sendFeedback.isPending}
                        className="rounded-md bg-primary px-3 py-1.5 text-sm text-white disabled:opacity-50"
                      >
                        {sendFeedback.isPending ? "Closing..." : "Yes, close ticket"}
                      </button>
                      <button
                        onClick={() => setConfirmingSolved(false)}
                        disabled={sendFeedback.isPending}
                        className="rounded-md border border-border-warm px-3 py-1.5 text-sm hover:bg-primary-light/20 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {suggestion.state === "accepted" && (
                  <p className="text-sm text-green-700">✓ Marked as solved — this ticket is now closed.</p>
                )}
                {suggestion.state === "rejected" && (
                  <p className="text-sm text-neutral-500">
                    You indicated this didn't solve the issue — it's been sent to IT support.
                  </p>
                )}
              </div>
            )}

            {suggestion && isAdmin && (
              <div>
                <div className="mb-3">
                  <p className="text-xs text-neutral-500">Suggested Resolution</p>
                  <p className="whitespace-pre-wrap text-sm">{suggestion.resolution_text}</p>
                </div>
                <div className="mb-3">
                  <p className="text-xs text-neutral-500">Confidence</p>
                  <p className="text-sm font-medium">{Math.round(suggestion.confidence * 100)}%</p>
                </div>
                {suggestion.evidence.length > 0 && (
                  <div className="mb-3">
                    <p className="mb-1 text-xs text-neutral-500">Evidence</p>
                    <ul className="space-y-1 text-sm">
                      {suggestion.evidence.map((e) => (
                        <li key={e.similar_ticket_id} className="text-neutral-600">
                          #{e.similar_ticket_id.slice(0, 8)} — {Math.round(e.similarity * 100)}% similar, {e.outcome}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
