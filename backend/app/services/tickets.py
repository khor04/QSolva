"""Business logic for the ticket lifecycle: AI enrichment on creation,
similarity retrieval for the resolution assistant, and claim/feedback transitions.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import AiSuggestion, Ticket, TicketAttachment, TicketEmbedding, TicketMessage, User
from app.services import ai
from app.services import issues as issue_clustering
from app.services.notifications import notify, notify_admins
from app.services.sla_policy import compute_due_dates

logger = logging.getLogger(__name__)

SIMILARITY_TOP_K = 5
# Fetch a wider candidate pool than we need, since some similar tickets end
# up with no usable resolution text and get filtered out below.
CANDIDATE_POOL_SIZE = SIMILARITY_TOP_K * 3
# Below this, the LLM is explicitly saying "these tickets don't share a
# consistent resolution" (per the synthesize_suggestion prompt) rather than
# offering a real fix — that's not a suggestion worth showing as "Try This
# First" with action buttons, it's the same as finding nothing at all.
MIN_SUGGESTION_CONFIDENCE = 0.4


def _now() -> datetime:
    return datetime.now(timezone.utc)


MAX_SEARCH_TERMS = 8


def _like_pattern(term: str) -> str:
    # Escape LIKE wildcards so a search for "100%" or "a_b" matches literally.
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def text_search_clause(query: str):
    """Every whitespace-separated term must appear somewhere in the ticket's
    title, description, an admin reply, or an accepted AI suggestion (the
    same two places services/issues.resolution_text_for reads a resolution
    from). Terms are ANDed rather than treated as one phrase, so "vpn
    timeout" still finds a ticket that says "timeout ... on the VPN"."""
    terms = query.split()[:MAX_SEARCH_TERMS]
    clauses = []
    for term in terms:
        pattern = _like_pattern(term)
        admin_reply = (
            select(TicketMessage.id)
            .join(User, User.id == TicketMessage.sender_id)
            .where(
                TicketMessage.ticket_id == Ticket.id,
                User.role == "admin",
                TicketMessage.body.ilike(pattern, escape="\\"),
            )
            .exists()
        )
        accepted_suggestion = (
            select(AiSuggestion.id)
            .where(
                AiSuggestion.ticket_id == Ticket.id,
                AiSuggestion.state == "accepted",
                AiSuggestion.resolution_text.ilike(pattern, escape="\\"),
            )
            .exists()
        )
        clauses.append(
            or_(
                Ticket.title.ilike(pattern, escape="\\"),
                Ticket.description.ilike(pattern, escape="\\"),
                admin_reply,
                accepted_suggestion,
            )
        )
    return and_(*clauses)


async def process_new_ticket(ticket_id: uuid.UUID) -> None:
    """Runs as a background task right after ticket creation: classifies
    priority, then (independently) embeds the ticket, retrieves similar
    resolved tickets, and synthesizes a resolution suggestion when there's
    enough evidence.

    Opens its own DB session rather than reusing the request's, since it
    executes after the request/response cycle (and that session) has ended.
    """
    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if ticket is None:
            return
        try:
            await _run_priority_stage(db, ticket)
            await _run_rag_stage(db, ticket)
            _notify_if_failed(db, ticket)
        except Exception:
            # FastAPI/Starlette swallows background task exceptions with no
            # log and no way for the client to know anything failed. Both
            # stages above already catch their own AI/DB errors and record
            # a status, so reaching here means something else broke.
            logger.exception("AI enrichment crashed unexpectedly for ticket %s", ticket_id)
    finally:
        db.close()


async def retry_enrichment(ticket_id: uuid.UUID) -> None:
    """Re-runs whichever AI stage(s) previously failed for an existing
    ticket (admin-triggered — see POST /tickets/{id}/retry-enrichment).
    Stages already at "success" (or "no_match" for RAG, which isn't an
    error) are left alone, so retrying doesn't reclassify an already-correct
    priority — that would risk re-firing new_critical_ticket — or redo a
    similarity search that already ran to completion."""
    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if ticket is None:
            return
        try:
            if ticket.ai_priority_status != "success":
                await _run_priority_stage(db, ticket)
            if ticket.ai_rag_status not in ("success", "no_match"):
                await _run_rag_stage(db, ticket)
            _notify_if_failed(db, ticket)
        except Exception:
            logger.exception("AI enrichment retry crashed unexpectedly for ticket %s", ticket_id)
    finally:
        db.close()


def _notify_if_failed(db: Session, ticket: Ticket) -> None:
    if ticket.ai_priority_status == "failed" or ticket.ai_rag_status == "failed":
        notify_admins(db, "suggestion_failed", ticket.id)
        db.commit()


def _attachment_urls(db: Session, ticket_id: uuid.UUID) -> list[str]:
    # Ordered oldest-first so that ai._fetch_image_parts's MAX_IMAGE_ATTACHMENTS
    # cap consistently keeps the earliest-uploaded screenshots rather than an
    # arbitrary DB-dependent subset.
    stmt = (
        select(TicketAttachment.file_url)
        .where(TicketAttachment.ticket_id == ticket_id)
        .order_by(TicketAttachment.created_at)
    )
    return list(db.execute(stmt).scalars())


async def _run_priority_stage(db: Session, ticket: Ticket) -> None:
    try:
        priority, confidence, reason = await ai.classify_priority(
            ticket.title, ticket.description, ticket.category, _attachment_urls(db, ticket.id)
        )
    except Exception:
        logger.exception("AI priority classification failed for ticket %s", ticket.id)
        ticket.ai_priority_status = "failed"
        db.commit()
        return

    was_critical = ticket.priority == "critical"
    ticket.priority = priority
    ticket.priority_confidence = confidence
    ticket.priority_reason = reason
    ticket.priority_source = "ai"
    ticket.ai_priority_status = "success"
    # Reclassifying can move the ticket onto a different SLA clock (e.g.
    # medium's business-hours clock to critical's 24/7 one).
    ticket.response_due_at, ticket.resolution_due_at = compute_due_dates(ticket.created_at, priority)
    # Tied to the transition into critical (not just the classification
    # result) so a retry that reclassifies an already-critical ticket as
    # critical again doesn't re-notify admins for no new reason.
    if priority == "critical" and not was_critical:
        notify_admins(db, "new_critical_ticket", ticket.id)
    db.commit()


async def _run_rag_stage(db: Session, ticket: Ticket) -> None:
    try:
        embedding = await ai.embed_text(f"{ticket.title}\n{ticket.description}")
        db.merge(
            TicketEmbedding(
                ticket_id=ticket.id,
                embedding=embedding,
                model_name=settings.embedding_model,
                updated_at=_now(),
            )
        )
        db.flush()

        await issue_clustering.assign_cluster(db, ticket, embedding)

        distance = TicketEmbedding.embedding.cosine_distance(embedding)
        stmt = (
            select(Ticket, TicketEmbedding, distance.label("distance"))
            .join(TicketEmbedding, TicketEmbedding.ticket_id == Ticket.id)
            .where(Ticket.status.in_(["resolved", "closed"]), Ticket.id != ticket.id)
            .order_by(distance)
            .limit(CANDIDATE_POOL_SIZE)
        )
        rows = db.execute(stmt).all()

        similar_for_ai = []
        evidence = []
        for similar_ticket, _embedding_row, dist in rows:
            # A ticket marked resolved/closed with no resolution text at all
            # (never replied to, never accepted a suggestion) isn't usable
            # evidence — including it would just feed the LLM a placeholder.
            resolution = issue_clustering.resolution_text_for(db, similar_ticket.id)
            if resolution is None:
                continue

            similarity = 1 - float(dist)
            similar_for_ai.append(
                {
                    "title": similar_ticket.title,
                    "description": similar_ticket.description,
                    "resolution": resolution,
                    "similarity": similarity,
                }
            )
            evidence.append(
                {
                    "similar_ticket_id": str(similar_ticket.id),
                    "similarity": similarity,
                    "resolution_snippet": resolution[:200],
                    "outcome": similar_ticket.status,
                }
            )
            if len(similar_for_ai) >= SIMILARITY_TOP_K:
                break

        if not similar_for_ai:
            ticket.ai_rag_status = "no_match"
            db.commit()
            return

        resolution_text, suggestion_confidence = await ai.synthesize_suggestion(
            ticket.title, ticket.description, similar_for_ai, _attachment_urls(db, ticket.id)
        )
        if resolution_text and suggestion_confidence >= MIN_SUGGESTION_CONFIDENCE:
            db.add(
                AiSuggestion(
                    ticket_id=ticket.id,
                    resolution_text=resolution_text,
                    confidence=suggestion_confidence,
                    state="available",
                    evidence=evidence,
                    created_at=_now(),
                )
            )
            ticket.ai_rag_status = "success"
        else:
            ticket.ai_rag_status = "no_match"
        db.commit()
    except Exception:
        logger.exception("AI RAG stage failed for ticket %s", ticket.id)
        db.rollback()
        ticket.ai_rag_status = "failed"
        db.commit()


def claim_ticket(db: Session, ticket: Ticket, admin_id: uuid.UUID) -> None:
    now = _now()
    ticket.assigned_admin_id = admin_id
    ticket.status = "in_progress"
    # Claiming counts as the first response for SLA purposes; only the first
    # claim does, so a later handoff doesn't move the deadline it was judged on.
    if ticket.first_response_at is None:
        ticket.first_response_at = now
    # Whoever escalated it is no longer relevant once someone takes ownership.
    ticket.escalated_by_admin_id = None
    ticket.escalation_reason = None
    ticket.updated_at = now
    db.commit()


def unassign_ticket(db: Session, ticket: Ticket) -> None:
    ticket.assigned_admin_id = None
    ticket.escalated_by_admin_id = None
    ticket.escalation_reason = None
    ticket.status = "open"
    ticket.updated_at = _now()
    db.commit()


def escalate_ticket(
    db: Session,
    ticket: Ticket,
    escalating_admin_id: uuid.UUID,
    reason: str | None = None,
    target_admin_id: uuid.UUID | None = None,
) -> None:
    """Escalation here means "I can't resolve this myself" rather than a
    move to a higher support tier (there is none). With a target it hands
    the ticket straight to that admin; without one it releases it back to
    the queue, unassigned, for whichever admin picks it up."""
    ticket.escalated_by_admin_id = escalating_admin_id
    ticket.escalation_reason = reason
    ticket.updated_at = _now()
    if target_admin_id is not None:
        # An internal reshuffle between admins: the ticket is still being
        # worked on, so staff isn't told it's been "escalated".
        ticket.assigned_admin_id = target_admin_id
        ticket.status = "in_progress"
        notify(db, target_admin_id, "ticket_escalated", ticket.id)
    else:
        ticket.assigned_admin_id = None
        ticket.status = "escalated"
        notify_admins(db, "ticket_escalated", ticket.id, exclude_user_id=escalating_admin_id)
        notify(db, ticket.staff_id, "ticket_escalated", ticket.id)
    db.commit()


def apply_feedback_to_ticket(db: Session, ticket: Ticket, suggestion: AiSuggestion | None, outcome: str) -> None:
    # Only record an outcome against a suggestion that hasn't already been
    # judged. A ticket can be closed later by other means (more back-and-forth
    # with an admin, self-resolved) after an earlier suggestion was already
    # marked rejected — that shouldn't retroactively flip it to "accepted"
    # and misrepresent that specific suggestion's evidence trail.
    if suggestion is not None and suggestion.state == "available":
        suggestion.state = "accepted" if outcome == "solved" else "rejected"

    if outcome == "solved":
        ticket.status = "closed"
        ticket.closed_at = _now()
    else:
        ticket.status = "in_progress"

    if ticket.assigned_admin_id:
        notify_type = "ticket_resolved" if outcome == "solved" else "ticket_updated"
        notify(db, ticket.assigned_admin_id, notify_type, ticket.id)

    ticket.updated_at = _now()
    db.commit()
