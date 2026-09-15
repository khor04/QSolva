export type TicketStatus = "open" | "in_progress" | "escalated" | "resolved" | "closed";
export type TicketPriority = "low" | "medium" | "high" | "critical";
export type TicketCategory = "network" | "hardware" | "software" | "email_account" | "access" | "other";
export type AiSuggestionState = "available" | "accepted" | "rejected" | "not_applicable";
export type PrioritySource = "ai" | "manual";
export type AiPriorityStatus = "pending" | "success" | "failed";
export type AiRagStatus = "pending" | "success" | "no_match" | "failed";
export type FeedbackOutcome = "solved" | "partially_solved" | "did_not_solve" | "wrong_recommendation" | "other";

export interface Ticket {
  id: string;
  staff_id: string;
  assigned_admin_id: string | null;
  escalated_by_admin_id: string | null;
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

export interface TicketDetailResponse {
  ticket: Ticket;
  messages: TicketMessage[];
  suggestion: AiSuggestion | null;
  attachments: TicketAttachment[];
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
  | "ticket_escalated";

export interface Notification {
  id: string;
  type: NotificationType;
  ticket_id: string | null;
  ticket_title: string | null;
  is_read: boolean;
  created_at: string;
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
