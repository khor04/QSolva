export type TicketStatus = "open" | "in_progress" | "escalated" | "resolved" | "closed";
export type TicketPriority = "low" | "medium" | "high" | "critical";
export type TicketCategory = "network" | "hardware" | "software" | "email_account" | "access" | "other";
export const TICKET_CATEGORIES: TicketCategory[] = ["network", "hardware", "software", "email_account", "access", "other"];
export type AiSuggestionState = "available" | "accepted" | "rejected" | "not_applicable";
export type PrioritySource = "ai" | "manual";
export type AiPriorityStatus = "pending" | "success" | "failed";
export type AiRagStatus = "pending" | "success" | "no_match" | "failed";
export type FeedbackOutcome = "solved" | "partially_solved" | "did_not_solve" | "wrong_recommendation" | "other";

export interface AdminWorkload {
  id: string;
  name: string;
  active_tickets: number;
  high_critical_tickets: number;
  overdue_tickets: number;
}

export interface Ticket {
  id: string;
  staff_id: string;
  assigned_admin_id: string | null;
  assigned_admin_name: string | null;
  escalated_by_admin_id: string | null;
  escalated_by_admin_name: string | null;
  title: string;
  description: string;
  category: TicketCategory;
  status: TicketStatus;
  priority: TicketPriority;
  priority_confidence: number | null;
  priority_reason: string | null;
  priority_source: PrioritySource;
  ai_priority_status: AiPriorityStatus;
  ai_rag_status: AiRagStatus;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  // When an admin first claimed/replied/resolved. The due times come from the
  // backend's SLA policy for the ticket's current priority.
  first_response_at: string | null;
  response_due_at: string;
  resolution_due_at: string;
  // Who posted the most recent message, and when — lets the admin queue flag
  // a ticket where an admin replied and nothing's moved since.
  last_message_by: "staff" | "admin" | null;
  last_message_at: string | null;
}

export interface TicketMessage {
  id: string;
  ticket_id: string;
  sender_id: string;
  body: string;
  created_at: string;
}

export interface AiSuggestionEvidence {
  similar_ticket_id: string;
  similarity: number;
  resolution_snippet: string;
  outcome: string;
}

export interface AiSuggestion {
  id: string;
  ticket_id: string;
  resolution_text: string;
  confidence: number;
  state: AiSuggestionState;
  evidence: AiSuggestionEvidence[];
  created_at: string;
}

export interface TicketAttachment {
  id: string;
  ticket_id: string;
  uploaded_by: string;
  file_url: string;
  created_at: string;
}

export type IncidentStatus = "active" | "resolved";

export interface RelatedActivity {
  active_reports: number;
  window_hours: number;
  someone_working_on_it: boolean;
  incident_status: IncidentStatus | null;
  incident_message: string | null;
}

export interface TicketDetailResponse {
  ticket: Ticket;
  messages: TicketMessage[];
  suggestion: AiSuggestion | null;
  attachments: TicketAttachment[];
  related_activity: RelatedActivity | null;
  // Admin-only; always null for the staff member who filed the ticket.
  escalation_reason: string | null;
}

export type NotificationType =
  | "ticket_updated"
  | "ticket_replied"
  | "ticket_resolved"
  | "resolution_confirm_needed"
  | "new_critical_ticket"
  | "staff_replied"
  | "suggestion_failed"
  | "sla_risk"
  | "ticket_escalated"
  | "incident_alert";

export interface Notification {
  id: string;
  type: NotificationType;
  ticket_id: string | null;
  ticket_title: string | null;
  message: string | null;
  is_read: boolean;
  created_at: string;
}

export interface AdminInviteCode {
  code: string;
  expires_at: string | null;
  max_uses: number;
}

export type IssueSeverity = "emerging" | "elevated" | "watch";
export type KbArticleStatus = "draft" | "published";

export interface IssueClusterSummary {
  id: string;
  label: string;
  category: TicketCategory;
  tickets_this_week: number;
  tickets_prev_week: number;
  pct_change: number | null;
  severity: IssueSeverity;
  article_status: KbArticleStatus | null;
  incident_status: IncidentStatus | null;
  incident_message: string | null;
  incident_updated_at: string | null;
}

export interface IssueTimelinePoint {
  date: string;
  count: number;
}

export interface IssueRelatedTicket {
  id: string;
  title: string;
  status: TicketStatus;
}

export interface KbArticle {
  question: string;
  answer: string;
  status: KbArticleStatus;
  generated_at: string | null;
  published_at: string | null;
}

export interface ResolutionEvidenceCounts {
  staff_confirmed: number;
  admin_resolved: number;
  unconfirmed: number;
}

export interface IssueClusterDetail extends IssueClusterSummary {
  symptoms: string[] | null;
  timeline: IssueTimelinePoint[];
  most_common_resolution: string | null;
  success_rate: number | null;
  evidence: ResolutionEvidenceCounts;
  related_tickets: IssueRelatedTicket[];
  article: KbArticle | null;
}

export interface HelpCenterArticleSummary {
  id: string;
  label: string;
  question: string;
  category: TicketCategory;
  solved_count: number;
  total_feedback: number;
}

export interface HelpCenterArticleDetail extends HelpCenterArticleSummary {
  answer: string;
  member_count: number;
}

export interface ActiveIncidentMatch {
  cluster_id: string;
  label: string;
  message: string | null;
}
