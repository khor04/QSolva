import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TicketStatus = Literal["open", "in_progress", "escalated", "resolved", "closed"]
TicketPriority = Literal["low", "medium", "high", "critical"]
TicketCategory = Literal["network", "hardware", "software", "email_account", "access", "other"]
AiSuggestionState = Literal["available", "accepted", "rejected", "not_applicable"]
FeedbackOutcome = Literal["solved", "partially_solved", "did_not_solve", "wrong_recommendation", "other"]
PrioritySource = Literal["ai", "manual"]
IncidentStatus = Literal["active", "resolved"]
AiPriorityStatus = Literal["pending", "success", "failed"]
AiRagStatus = Literal["pending", "success", "no_match", "failed"]
NotificationType = Literal[
    "ticket_updated",
    "ticket_replied",
    "ticket_resolved",
    "resolution_confirm_needed",
    "new_critical_ticket",
    "staff_replied",
    "ticket_escalated",
    "suggestion_failed",
    "sla_risk",
    "incident_alert",
]


class TicketCreate(BaseModel):
    title: str
    description: str
    category: TicketCategory
    # Set when the reporter clicked "Doesn't fix it — submit anyway" on the
    # pre-submit Help Center match (see NewTicket.tsx) — which cluster's
    # already-published answer they tried first and it didn't work.
    already_tried_cluster_id: uuid.UUID | None = None


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    staff_id: uuid.UUID
    assigned_admin_id: uuid.UUID | None
    assigned_admin_name: str | None
    escalated_by_admin_id: uuid.UUID | None
    escalated_by_admin_name: str | None
    # None means not yet grouped into a recurring-issue cluster — used on the
    # admin ticket view to decide whether "Escalate to new incident" applies
    # (a ticket already in a cluster should use that cluster's own incident
    # flow on the Issues page instead of creating a second, overlapping one).
    cluster_id: uuid.UUID | None
    already_tried_cluster_id: uuid.UUID | None
    already_tried_label: str | None
    title: str
    description: str
    category: TicketCategory
    status: TicketStatus
    priority: TicketPriority
    priority_confidence: float | None
    priority_reason: str | None
    priority_source: PrioritySource
    ai_priority_status: AiPriorityStatus
    ai_rag_status: AiRagStatus
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    first_response_at: datetime | None
    response_due_at: datetime
    resolution_due_at: datetime
    # Who posted the most recent message and when — lets the admin queue flag
    # "admin replied, nothing's moved since" without a per-ticket message
    # query. See routers/tickets.post_message.
    last_message_by: Literal["staff", "admin"] | None
    last_message_at: datetime | None


class MessageCreate(BaseModel):
    body: str
    # Lets an admin resolve in the same roundtrip as their reply, instead of
    # replying and then having to remember a second click. Ignored (and
    # rejected, see routers/tickets.post_message) for staff.
    mark_resolved: bool = False


class EscalateRequest(BaseModel):
    reason: str | None = Field(None, max_length=1000)
    # None = release back to the queue; set = hand off straight to that admin.
    target_admin_id: uuid.UUID | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime


class SuggestionEvidenceItem(BaseModel):
    similar_ticket_id: str
    similarity: float
    resolution_snippet: str
    outcome: str


class SuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    resolution_text: str
    confidence: float
    state: AiSuggestionState
    evidence: list[SuggestionEvidenceItem]
    created_at: datetime


class AttachmentCreate(BaseModel):
    file_url: str


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    uploaded_by: uuid.UUID
    file_url: str
    created_at: datetime


class RelatedActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    active_reports: int
    window_hours: int
    someone_working_on_it: bool
    incident_status: IncidentStatus | None
    incident_message: str | None


class TicketDetailOut(BaseModel):
    ticket: TicketOut
    messages: list[MessageOut]
    suggestion: SuggestionOut | None
    attachments: list[AttachmentOut]
    # None when there's nothing worth surfacing yet — see
    # services/issues.related_activity_for.
    related_activity: RelatedActivityOut | None = None
    # Admin-only: always None for the staff member who filed the ticket.
    escalation_reason: str | None = None


class FeedbackCreate(BaseModel):
    outcome: FeedbackOutcome
    comment: str | None = None


IssueSeverity = Literal["emerging", "elevated", "watch"]
KbArticleStatus = Literal["draft", "published"]


class IssueTimelinePoint(BaseModel):
    date: str
    count: int


class IssueRelatedTicket(BaseModel):
    id: uuid.UUID
    title: str
    status: TicketStatus


class KbArticle(BaseModel):
    question: str
    answer: str
    status: KbArticleStatus
    generated_at: datetime | None
    published_at: datetime | None


class IssueClusterSummary(BaseModel):
    id: uuid.UUID
    label: str
    category: TicketCategory
    tickets_this_week: int
    tickets_prev_week: int
    pct_change: float | None
    severity: IssueSeverity
    article_status: KbArticleStatus | None
    incident_status: IncidentStatus | None
    incident_message: str | None
    incident_updated_at: datetime | None


class ResolutionEvidenceCounts(BaseModel):
    staff_confirmed: int
    admin_resolved: int
    unconfirmed: int


class IssueClusterDetail(IssueClusterSummary):
    symptoms: list[str] | None
    timeline: list[IssueTimelinePoint]
    most_common_resolution: str | None
    success_rate: float | None
    evidence: ResolutionEvidenceCounts
    related_tickets: list[IssueRelatedTicket]
    article: KbArticle | None


class ArticleEdit(BaseModel):
    question: str
    answer: str


class IncidentStart(BaseModel):
    message: str
    notify_all_staff: bool = False


class IncidentResolve(BaseModel):
    resolution_text: str


class ActiveIncidentCheck(BaseModel):
    title: str
    description: str


class ActiveIncidentMatch(BaseModel):
    cluster_id: uuid.UUID
    label: str
    # A cluster can satisfy either or both — an active incident is the
    # stronger signal, a published article means there's already a
    # self-service answer. Both are admin-gated (see start_incident /
    # publish_article), so it's safe to show a reporter either one; an
    # unreviewed cluster never reaches this response regardless of size.
    is_active_incident: bool
    is_published_article: bool
    message: str | None
    article_question: str | None = None
    article_answer: str | None = None


class NewIncidentCreate(BaseModel):
    """Declares a brand-new incident with no existing recurring-issue
    cluster behind it (e.g. IT knows about an outage before any ticket has
    been filed). description seeds the cluster's embedding so future
    tickets can still auto-join it, the same as an algorithmically-detected
    cluster would."""

    label: str
    category: TicketCategory
    description: str
    message: str
    notify_all_staff: bool = False


class HelpCenterArticleSummary(BaseModel):
    id: uuid.UUID
    label: str
    question: str
    category: TicketCategory
    solved_count: int
    total_feedback: int


class HelpCenterArticleDetail(HelpCenterArticleSummary):
    answer: str
    member_count: int


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: NotificationType
    ticket_id: uuid.UUID | None
    ticket_title: str | None
    message: str | None
    is_read: bool
    created_at: datetime


class AdminInviteCodeCreate(BaseModel):
    expires_in_days: int | None = 7
    max_uses: int = 1


class AdminInviteCodeOut(BaseModel):
    code: str
    expires_at: datetime | None
    max_uses: int


class AdminWorkload(BaseModel):
    id: uuid.UUID
    name: str
    active_tickets: int
    high_critical_tickets: int
    overdue_tickets: int


class PriorityDistribution(BaseModel):
    critical: int
    high: int
    medium: int
    low: int


class DashboardTrendPoint(BaseModel):
    date: str
    count: int


class DashboardEmergingIssue(BaseModel):
    id: uuid.UUID
    label: str
    tickets_this_week: int
    pct_change: float | None
    severity: IssueSeverity


class AiPerformance(BaseModel):
    acceptance_rate: float | None
    coverage_rate: float | None
    deflection_rate: float | None


class DashboardStats(BaseModel):
    total_tickets: int
    open_tickets: int
    overdue_tickets: int
    resolved_tickets: int
    closed_tickets: int
    recurring_issues_count: int
    priority_distribution: PriorityDistribution
    volume_trend: list[DashboardTrendPoint]
    emerging_issues: list[DashboardEmergingIssue]
    ai_performance: AiPerformance
