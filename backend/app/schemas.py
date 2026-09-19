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


class MessageCreate(BaseModel):
    body: str


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
    message: str | None


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
