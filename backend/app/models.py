import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, Numeric, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

user_role = ENUM("staff", "admin", name="user_role", create_type=False)
ticket_status_enum = ENUM(
    "open", "in_progress", "escalated", "resolved", "closed",
    name="ticket_status", create_type=False,
)
ticket_priority_enum = ENUM("low", "medium", "high", "critical", name="ticket_priority", create_type=False)
ticket_category_enum = ENUM(
    "network", "hardware", "software", "email_account", "access", "other",
    name="ticket_category", create_type=False,
)
priority_source_enum = ENUM("ai", "manual", name="priority_source", create_type=False)
ai_suggestion_state_enum = ENUM(
    "available", "accepted", "rejected", "not_applicable",
    name="ai_suggestion_state", create_type=False,
)
feedback_outcome_enum = ENUM(
    "solved", "partially_solved", "did_not_solve", "wrong_recommendation", "other",
    name="feedback_outcome", create_type=False,
)
notification_type_enum = ENUM(
    "ticket_updated", "ticket_replied", "ticket_resolved", "resolution_confirm_needed",
    "new_critical_ticket", "staff_replied", "suggestion_failed", "sla_risk", "ticket_escalated",
    name="notification_type", create_type=False,
)
kb_article_status_enum = ENUM("draft", "published", name="kb_article_status", create_type=False)
ai_priority_status_enum = ENUM("pending", "success", "failed", name="ai_priority_status", create_type=False)
ai_rag_status_enum = ENUM("pending", "success", "no_match", "failed", name="ai_rag_status", create_type=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    role: Mapped[str] = mapped_column(user_role, default="staff")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    assigned_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    escalated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("issue_clusters.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(ticket_category_enum)
    status: Mapped[str] = mapped_column(ticket_status_enum, default="open")
    priority: Mapped[str] = mapped_column(ticket_priority_enum, default="medium")
    priority_confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    priority_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_source: Mapped[str] = mapped_column(priority_source_enum, default="ai")
    # Tracked independently of priority_confidence/AiSuggestion existence so a
    # failed stage can be retried without redoing one that already succeeded,
    # and so "no similar cases found" (no_match) is distinguishable in the UI
    # from "the AI call itself failed" (failed, retryable).
    ai_priority_status: Mapped[str] = mapped_column(ai_priority_status_enum, default="pending")
    ai_rag_status: Mapped[str] = mapped_column(ai_rag_status_enum, default="pending")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    messages: Mapped[list["TicketMessage"]] = relationship(back_populates="ticket", order_by="TicketMessage.created_at")
    suggestions: Mapped[list["AiSuggestion"]] = relationship(back_populates="ticket", order_by="AiSuggestion.created_at.desc()")
    embedding: Mapped["TicketEmbedding | None"] = relationship(back_populates="ticket", uselist=False)


class TicketMessage(Base):
    __tablename__ = "ticket_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"))
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

    ticket: Mapped["Ticket"] = relationship(back_populates="messages")


class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    file_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class TicketEmbedding(Base):
    __tablename__ = "ticket_embeddings"

    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(768))
    model_name: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

    ticket: Mapped["Ticket"] = relationship(back_populates="embedding")


class AiSuggestion(Base):
    __tablename__ = "ai_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"))
    resolution_text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Numeric)
    state: Mapped[str] = mapped_column(ai_suggestion_state_enum, default="available")
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

    ticket: Mapped["Ticket"] = relationship(back_populates="suggestions")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ai_suggestion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_suggestions.id"), nullable=True)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"))
    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    outcome: Mapped[str] = mapped_column(feedback_outcome_enum)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class IssueCluster(Base):
    """A recurring/systemic problem: tickets are incrementally grouped in
    here by embedding similarity (see services/issues.py) rather than by
    any explicit admin action."""

    __tablename__ = "issue_clusters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(ticket_category_enum)
    centroid_embedding: Mapped[list[float]] = mapped_column(Vector(768))
    member_count: Mapped[int] = mapped_column(default=1)
    symptoms: Mapped[list | None] = mapped_column(JSON, nullable=True)
    symptoms_updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    article_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_status: Mapped[str | None] = mapped_column(kb_article_status_enum, nullable=True)
    article_generated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    article_published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(notification_type_enum)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
