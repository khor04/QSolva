import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.deps import get_current_user, require_admin
from app.db import get_db
from app.models import AiSuggestion, Feedback, Ticket, TicketAttachment, TicketMessage, User
from app.schemas import (
    ActiveIncidentCheck,
    ActiveIncidentMatch,
    AttachmentCreate,
    AttachmentOut,
    EscalateRequest,
    FeedbackCreate,
    MessageCreate,
    MessageOut,
    TicketCategory,
    TicketCreate,
    TicketDetailOut,
    TicketOut,
    TicketUpdate,
)
from app.services import ai
from app.services import tickets as ticket_service
from app.services.issues import match_known_issue, related_activity_for
from app.services.notifications import notify, notify_admins

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_ticket_or_404(db: Session, ticket_id: uuid.UUID) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def _authorize_ticket_access(ticket: Ticket, user: User) -> None:
    if user.role == "admin":
        return
    if ticket.staff_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ticket")


def _ensure_not_done(ticket: Ticket) -> None:
    """Once a ticket is resolved (awaiting staff confirmation) or closed
    (confirmed), claim/unassign/escalate/re-resolve no longer make sense.
    The only way out of "resolved" is the staff feedback endpoint, which
    doesn't go through this check."""
    if ticket.status in ("resolved", "closed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ticket is already {ticket.status}",
        )


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "staff":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only staff can submit tickets")

    now = _now()
    # Starts on the "medium" clock — reclassified (and due dates recomputed)
    # once AI priority classification finishes, see _run_priority_stage.
    response_due_at, resolution_due_at = ticket_service.compute_due_dates(now, "medium")
    ticket = Ticket(
        staff_id=user.id,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        status="open",
        priority="medium",
        priority_source="ai",
        ai_priority_status="pending",
        ai_rag_status="pending",
        already_tried_cluster_id=payload.already_tried_cluster_id,
        created_at=now,
        updated_at=now,
        response_due_at=response_due_at,
        resolution_due_at=resolution_due_at,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/start-enrichment", status_code=status.HTTP_202_ACCEPTED)
def start_enrichment(
    ticket_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kicks off AI priority classification + resolution-suggestion enrichment
    for a just-created ticket. Split out from create_ticket and called by the
    client only after any attachment uploads have finished, so the AI stages
    see attached screenshots that are already linked in the DB rather than
    racing the client's upload (create_ticket returns, and returns fast,
    well before a client-side Supabase Storage upload + attachment POST can
    complete)."""
    ticket = _get_ticket_or_404(db, ticket_id)
    _authorize_ticket_access(ticket, user)

    background_tasks.add_task(_run_process_new_ticket, ticket.id)
    return {"status": "started"}


def _run_process_new_ticket(ticket_id: uuid.UUID) -> None:
    import asyncio

    asyncio.run(ticket_service.process_new_ticket(ticket_id))


@router.post("/check-active-incident", response_model=ActiveIncidentMatch | None)
async def check_active_incident(
    payload: ActiveIncidentCheck,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Called from the New Ticket form before submission, so a reporter can
    be told "this looks like a known issue" instead of filing a duplicate of
    something IT already knows about — either a declared active incident, or
    an issue with a published Help Center answer. See
    services/issues.match_known_issue for why this is cheap (no AI call at
    all) when neither exists yet."""
    cluster = await match_known_issue(db, payload.title, payload.description)
    if cluster is None:
        return None
    is_active = cluster.incident_status == "active"
    is_published = cluster.article_status == "published"
    return ActiveIncidentMatch(
        cluster_id=cluster.id,
        label=cluster.label,
        is_active_incident=is_active,
        is_published_article=is_published,
        message=cluster.incident_message if is_active else None,
        article_question=cluster.article_question if is_published else None,
        article_answer=cluster.article_answer if is_published else None,
    )


@router.post("/{ticket_id}/retry-enrichment", response_model=TicketOut)
def retry_enrichment(
    ticket_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ticket = _get_ticket_or_404(db, ticket_id)

    # Atomically claim each failed stage by flipping it to "pending" only if
    # it's still "failed" right now. A second concurrent retry (double-click,
    # or two admins on the same ticket) then claims 0 rows for whatever the
    # first request already grabbed, instead of both kicking off duplicate
    # Gemini calls for the same ticket.
    claimed_priority = (
        db.execute(
            update(Ticket)
            .where(Ticket.id == ticket.id, Ticket.ai_priority_status == "failed")
            .values(ai_priority_status="pending")
        ).rowcount
        > 0
    )
    claimed_rag = (
        db.execute(
            update(Ticket)
            .where(Ticket.id == ticket.id, Ticket.ai_rag_status == "failed")
            .values(ai_rag_status="pending")
        ).rowcount
        > 0
    )
    db.commit()

    if not claimed_priority and not claimed_rag:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nothing to retry — AI analysis already completed, or a retry is already in progress",
        )

    db.refresh(ticket)
    background_tasks.add_task(_run_retry_enrichment, ticket.id)
    return ticket


def _run_retry_enrichment(ticket_id: uuid.UUID) -> None:
    import asyncio

    asyncio.run(ticket_service.retry_enrichment(ticket_id))


@router.get("", response_model=list[TicketOut])
def list_my_tickets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = (
        select(Ticket)
        .where(Ticket.staff_id == user.id)
        .order_by(Ticket.updated_at.desc())
        .options(selectinload(Ticket.assigned_admin), selectinload(Ticket.escalated_by_admin))
    )
    return list(db.execute(stmt).scalars())


@router.get("/queue", response_model=list[TicketOut])
def list_queue(
    q: str | None = Query(None, max_length=200),
    category: TicketCategory | None = None,
    # created_after is inclusive, created_before exclusive, so the client can
    # express "the whole of <day>" as [local midnight, next local midnight)
    # without this endpoint needing to know the viewer's timezone.
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Ticket)
        .order_by(Ticket.priority.desc(), Ticket.created_at.asc())
        .options(selectinload(Ticket.assigned_admin), selectinload(Ticket.escalated_by_admin))
    )
    if q and q.strip():
        stmt = stmt.where(ticket_service.text_search_clause(q))
    if category is not None:
        stmt = stmt.where(Ticket.category == category)
    if created_after is not None:
        stmt = stmt.where(Ticket.created_at >= created_after)
    if created_before is not None:
        stmt = stmt.where(Ticket.created_at < created_before)
    return list(db.execute(stmt).scalars())


@router.get("/{ticket_id}", response_model=TicketDetailOut)
def get_ticket_detail(ticket_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ticket = _get_ticket_or_404(db, ticket_id)
    _authorize_ticket_access(ticket, user)

    messages = list(
        db.execute(
            select(TicketMessage).where(TicketMessage.ticket_id == ticket.id).order_by(TicketMessage.created_at)
        ).scalars()
    )
    suggestion = db.execute(
        select(AiSuggestion)
        .where(AiSuggestion.ticket_id == ticket.id)
        .order_by(AiSuggestion.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    attachments = list(
        db.execute(
            select(TicketAttachment)
            .where(TicketAttachment.ticket_id == ticket.id)
            .order_by(TicketAttachment.created_at)
        ).scalars()
    )

    related_activity = related_activity_for(db, ticket)

    return TicketDetailOut(
        ticket=ticket,
        messages=messages,
        suggestion=suggestion,
        attachments=attachments,
        related_activity=related_activity,
        escalation_reason=ticket.escalation_reason if user.role == "admin" else None,
    )


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: uuid.UUID,
    payload: TicketUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ticket = _get_ticket_or_404(db, ticket_id)
    if payload.status == "escalated":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use POST /tickets/{id}/escalate to escalate a ticket",
        )
    if payload.status == "open" and ticket.assigned_admin_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use POST /tickets/{id}/unassign to release an assigned ticket back to the queue",
        )
    if payload.status == "in_progress":
        # No generic path in: claim (open/escalated -> in_progress) and
        # handoff (POST .../escalate with a target) both pair it with
        # assigning an admin and stamping first_response_at, which a bare
        # status write here would skip.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use POST /tickets/{id}/claim, or /escalate with a target_admin_id, to move a ticket to in_progress",
        )
    if payload.status is not None:
        _ensure_not_done(ticket)
        ticket.status = payload.status
        if ticket.first_response_at is None:
            ticket.first_response_at = _now()
        if payload.status == "resolved":
            ticket.resolved_at = _now()
            notify(db, ticket.staff_id, "resolution_confirm_needed", ticket.id)
        else:
            if payload.status == "closed":
                ticket.closed_at = _now()
            notify(db, ticket.staff_id, "ticket_updated", ticket.id)
    elif payload.priority is not None:
        notify(db, ticket.staff_id, "ticket_updated", ticket.id)
    if payload.priority is not None:
        ticket.priority = payload.priority
        ticket.priority_source = "manual"
        # These describe the AI's own assessment; once an admin overrides
        # the priority they no longer apply and would be misleading if shown.
        ticket.priority_confidence = None
        ticket.priority_reason = None
        # A different priority can mean a different SLA clock entirely
        # (business-hours vs 24/7), not just a different offset — recompute
        # both deadlines from the original creation time.
        ticket.response_due_at, ticket.resolution_due_at = ticket_service.compute_due_dates(
            ticket.created_at, payload.priority
        )
    ticket.updated_at = _now()
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def post_message(
    ticket_id: uuid.UUID,
    payload: MessageCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = _get_ticket_or_404(db, ticket_id)
    _authorize_ticket_access(ticket, user)

    if payload.mark_resolved:
        if user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can resolve a ticket")
        # Same guard as PATCH .../resolved — checked before writing anything,
        # so a stale double-submit doesn't post the reply and then 409 on the
        # status change, leaving the reply orphaned with no resolution.
        _ensure_not_done(ticket)

    now = _now()
    message = TicketMessage(ticket_id=ticket.id, sender_id=user.id, body=payload.body, created_at=now)
    db.add(message)
    ticket.updated_at = now
    ticket.last_message_by = user.role
    ticket.last_message_at = now

    if user.role == "staff":
        if ticket.assigned_admin_id:
            notify(db, ticket.assigned_admin_id, "staff_replied", ticket.id)
        else:
            notify_admins(db, "staff_replied", ticket.id)
    else:
        if ticket.first_response_at is None:
            ticket.first_response_at = now
        if payload.mark_resolved:
            ticket.status = "resolved"
            ticket.resolved_at = now
            # More specific than the generic "admin replied" notice below —
            # matches what PATCH .../resolved sends, and avoids notifying the
            # staff member twice for one action.
            notify(db, ticket.staff_id, "resolution_confirm_needed", ticket.id)
        else:
            notify(db, ticket.staff_id, "ticket_replied", ticket.id)

    db.commit()
    db.refresh(message)
    return message


@router.post("/{ticket_id}/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
def add_attachment(
    ticket_id: uuid.UUID,
    payload: AttachmentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Records an attachment after the file has already been uploaded directly
    to Supabase Storage from the client (see lib/storage.ts on the frontend).
    This endpoint just links the resulting URL to the ticket."""
    ticket = _get_ticket_or_404(db, ticket_id)
    _authorize_ticket_access(ticket, user)

    existing_count = db.execute(
        select(func.count()).select_from(TicketAttachment).where(TicketAttachment.ticket_id == ticket.id)
    ).scalar_one()
    if existing_count >= ai.MAX_IMAGE_ATTACHMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A ticket can have at most {ai.MAX_IMAGE_ATTACHMENTS} attachments",
        )

    attachment = TicketAttachment(
        ticket_id=ticket.id,
        uploaded_by=user.id,
        file_url=payload.file_url,
        created_at=_now(),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


@router.post("/{ticket_id}/claim", response_model=TicketOut)
def claim_ticket(ticket_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    ticket = _get_ticket_or_404(db, ticket_id)
    _ensure_not_done(ticket)
    if ticket.assigned_admin_id == admin.id:
        return ticket
    if ticket.assigned_admin_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Already assigned to {ticket.assigned_admin_name or 'another admin'}",
        )
    ticket_service.claim_ticket(db, ticket, admin.id)
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/unassign", response_model=TicketOut)
def unassign_ticket(ticket_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    ticket = _get_ticket_or_404(db, ticket_id)
    _ensure_not_done(ticket)
    # Otherwise any admin could unassign someone else's ticket and then
    # claim it, sidestepping the claim guard.
    if ticket.assigned_admin_id != admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only the assigned admin can unassign this ticket",
        )
    ticket_service.unassign_ticket(db, ticket)
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/escalate", response_model=TicketOut)
def escalate_ticket(
    ticket_id: uuid.UUID,
    payload: EscalateRequest | None = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ticket = _get_ticket_or_404(db, ticket_id)
    _ensure_not_done(ticket)
    if ticket.assigned_admin_id != admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only the assigned admin can escalate this ticket",
        )
    payload = payload or EscalateRequest()
    if payload.target_admin_id is not None:
        target = db.get(User, payload.target_admin_id)
        if target is None or target.role != "admin" or target.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target must be an active admin")
        if target.id == admin.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can't hand a ticket to yourself")
    ticket_service.escalate_ticket(
        db,
        ticket,
        admin.id,
        reason=(payload.reason or "").strip() or None,
        target_admin_id=payload.target_admin_id,
    )
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/feedback", status_code=status.HTTP_201_CREATED)
def submit_feedback(
    ticket_id: uuid.UUID,
    payload: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ticket = _get_ticket_or_404(db, ticket_id)
    _authorize_ticket_access(ticket, user)

    suggestion = db.execute(
        select(AiSuggestion)
        .where(AiSuggestion.ticket_id == ticket.id)
        .order_by(AiSuggestion.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    feedback = Feedback(
        ai_suggestion_id=suggestion.id if suggestion else None,
        ticket_id=ticket.id,
        staff_id=user.id,
        outcome=payload.outcome,
        comment=payload.comment,
        created_at=_now(),
    )
    db.add(feedback)
    ticket_service.apply_feedback_to_ticket(db, ticket, suggestion, payload.outcome)
    return {"status": "recorded"}
