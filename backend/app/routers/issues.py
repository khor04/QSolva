import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import Feedback, IssueCluster, Ticket, User
from app.schemas import (
    ArticleEdit,
    IncidentResolve,
    IncidentStart,
    IssueClusterDetail,
    IssueClusterSummary,
    IssueRelatedTicket,
    IssueSeverity,
    IssueTimelinePoint,
    KbArticle,
    NewIncidentCreate,
    ResolutionEvidenceCounts,
)
from app.services.issues import (
    create_incident_from_scratch,
    escalate_ticket_to_incident,
    gather_evidence,
    resolve_incident,
    start_incident,
)

router = APIRouter(prefix="/issues", tags=["issues"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _week_counts(db: Session, cluster_id: uuid.UUID) -> tuple[int, int]:
    now = _now()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    this_week = db.execute(
        select(func.count()).select_from(Ticket).where(Ticket.cluster_id == cluster_id, Ticket.created_at >= week_ago)
    ).scalar_one()
    prev_week = db.execute(
        select(func.count())
        .select_from(Ticket)
        .where(
            Ticket.cluster_id == cluster_id,
            Ticket.created_at >= two_weeks_ago,
            Ticket.created_at < week_ago,
        )
    ).scalar_one()
    return this_week, prev_week


def _pct_change(this_week: int, prev_week: int) -> float | None:
    if prev_week == 0:
        return None
    return round((this_week - prev_week) / prev_week * 100, 1)


def _severity(tickets_this_week: int, pct_change: float | None) -> IssueSeverity:
    # Volume is the primary signal (it's what admins actually have to triage);
    # % growth only overrides it for genuinely explosive, still-small spikes.
    if tickets_this_week >= 15 or (pct_change is not None and pct_change >= 300):
        return "emerging"
    if tickets_this_week >= 8:
        return "elevated"
    return "watch"


_SEVERITY_RANK: dict[IssueSeverity, int] = {"emerging": 0, "elevated": 1, "watch": 2}


def _to_summary(db: Session, cluster: IssueCluster) -> IssueClusterSummary:
    this_week, prev_week = _week_counts(db, cluster.id)
    pct = _pct_change(this_week, prev_week)
    return IssueClusterSummary(
        id=cluster.id,
        label=cluster.label,
        category=cluster.category,
        tickets_this_week=this_week,
        tickets_prev_week=prev_week,
        pct_change=pct,
        severity=_severity(this_week, pct),
        article_status=cluster.article_status,
        incident_status=cluster.incident_status,
        incident_message=cluster.incident_message,
        incident_updated_at=cluster.incident_updated_at,
    )


@router.get("", response_model=list[IssueClusterSummary])
def list_issues(_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    # A single-ticket "cluster" isn't a recurring issue yet — unless an admin
    # has explicitly declared it an incident (see create_incident/escalate_ticket
    # below), in which case it belongs on this page regardless of size.
    clusters = (
        db.execute(select(IssueCluster).where(or_(IssueCluster.member_count >= 2, IssueCluster.incident_status == "active")))
        .scalars()
        .all()
    )
    summaries = [_to_summary(db, c) for c in clusters]
    # Active incidents first regardless of severity — they're the ones
    # admins need to act on/track to resolution — then by severity, then by
    # ticket volume within each severity tier.
    summaries.sort(key=lambda s: (s.incident_status != "active", _SEVERITY_RANK[s.severity], -s.tickets_this_week))
    return summaries


@router.post("", response_model=IssueClusterDetail, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: NewIncidentCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Declares an incident with no existing recurring-issue cluster behind
    it — for when IT already knows about a problem (e.g. from internal
    monitoring) before any matching ticket has been filed. See
    services/issues.create_incident_from_scratch."""
    if not payload.label.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Label can't be empty")
    if not payload.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incident message can't be empty")
    cluster = await create_incident_from_scratch(
        db,
        label=payload.label.strip(),
        category=payload.category,
        description=payload.description.strip(),
        message=payload.message.strip(),
        admin=admin,
        notify_all_staff=payload.notify_all_staff,
    )
    db.refresh(cluster)
    return _build_detail(db, cluster)


@router.post("/from-ticket/{ticket_id}", response_model=IssueClusterDetail, status_code=status.HTTP_201_CREATED)
def escalate_ticket(
    ticket_id: uuid.UUID,
    payload: IncidentStart,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Declares a new incident seeded from a single, not-yet-clustered
    ticket, for an admin who spots a first report that's clearly about to
    become widespread and doesn't want to wait for 2+ similar tickets to
    land before acting. See services/issues.escalate_ticket_to_incident."""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if not payload.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incident message can't be empty")
    try:
        cluster = escalate_ticket_to_incident(
            db, ticket, payload.message.strip(), admin, notify_all_staff=payload.notify_all_staff
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    db.refresh(cluster)
    return _build_detail(db, cluster)


def _build_detail(db: Session, cluster: IssueCluster) -> IssueClusterDetail:
    summary = _to_summary(db, cluster)

    since = _now() - timedelta(days=14)
    rows = db.execute(
        select(func.date(Ticket.created_at), func.count())
        .where(Ticket.cluster_id == cluster.id, Ticket.created_at >= since)
        .group_by(func.date(Ticket.created_at))
        .order_by(func.date(Ticket.created_at))
    ).all()
    timeline = [IssueTimelinePoint(date=str(day), count=count) for day, count in rows]

    related = (
        db.execute(select(Ticket).where(Ticket.cluster_id == cluster.id).order_by(Ticket.created_at.desc()).limit(50))
        .scalars()
        .all()
    )
    related_out = [IssueRelatedTicket(id=t.id, title=t.title, status=t.status) for t in related]

    # Most common resolution: prefer a staff-confirmed one, but fall back to
    # an admin's own resolution if nobody has confirmed anything yet — that's
    # still real knowledge, not nothing (see services/issues.gather_evidence).
    evidence = gather_evidence(db, cluster.id)
    most_common_resolution = evidence.best_resolution
    evidence_counts = ResolutionEvidenceCounts(
        staff_confirmed=len(evidence.staff_confirmed),
        admin_resolved=len(evidence.admin_resolved),
        unconfirmed=evidence.unconfirmed_count,
    )

    feedback_outcomes = (
        db.execute(
            select(Feedback.outcome).join(Ticket, Ticket.id == Feedback.ticket_id).where(Ticket.cluster_id == cluster.id)
        )
        .scalars()
        .all()
    )
    success_rate = None
    if feedback_outcomes:
        solved = sum(1 for outcome in feedback_outcomes if outcome == "solved")
        success_rate = round(solved / len(feedback_outcomes) * 100, 1)

    article = None
    if cluster.article_question and cluster.article_answer and cluster.article_status:
        article = KbArticle(
            question=cluster.article_question,
            answer=cluster.article_answer,
            status=cluster.article_status,
            generated_at=cluster.article_generated_at,
            published_at=cluster.article_published_at,
        )

    return IssueClusterDetail(
        **summary.model_dump(),
        symptoms=cluster.symptoms,
        timeline=timeline,
        most_common_resolution=most_common_resolution,
        success_rate=success_rate,
        evidence=evidence_counts,
        related_tickets=related_out,
        article=article,
    )


def _get_cluster_or_404(db: Session, cluster_id: uuid.UUID) -> IssueCluster:
    cluster = db.get(IssueCluster, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return cluster


@router.get("/{cluster_id}", response_model=IssueClusterDetail)
def get_issue(cluster_id: uuid.UUID, _admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    cluster = _get_cluster_or_404(db, cluster_id)
    return _build_detail(db, cluster)


@router.post("/{cluster_id}/article/publish", response_model=IssueClusterDetail)
def publish_article(cluster_id: uuid.UUID, _admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    cluster = _get_cluster_or_404(db, cluster_id)
    if not cluster.article_question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No draft article to publish yet")
    cluster.article_status = "published"
    cluster.article_published_at = _now()
    db.commit()
    db.refresh(cluster)
    return _build_detail(db, cluster)


@router.post("/{cluster_id}/article/unpublish", response_model=IssueClusterDetail)
def unpublish_article(cluster_id: uuid.UUID, _admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    cluster = _get_cluster_or_404(db, cluster_id)
    if cluster.article_status == "published":
        cluster.article_status = "draft"
        db.commit()
        db.refresh(cluster)
    return _build_detail(db, cluster)


@router.patch("/{cluster_id}/article", response_model=IssueClusterDetail)
def edit_article(
    cluster_id: uuid.UUID,
    payload: ArticleEdit,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    cluster = _get_cluster_or_404(db, cluster_id)
    cluster.article_question = payload.question
    cluster.article_answer = payload.answer
    if cluster.article_status is None:
        cluster.article_status = "draft"
    db.commit()
    db.refresh(cluster)
    return _build_detail(db, cluster)


@router.post("/{cluster_id}/incident/start", response_model=IssueClusterDetail)
def start_cluster_incident(
    cluster_id: uuid.UUID,
    payload: IncidentStart,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Declares this cluster an active incident (or updates its status
    message if already active), notifying every staff member with a
    still-open ticket in it — so "12 others reported this" on their ticket
    becomes "IT is aware, here's the status" instead."""
    cluster = _get_cluster_or_404(db, cluster_id)
    if not payload.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incident message can't be empty")
    start_incident(db, cluster, payload.message.strip(), admin, notify_all_staff=payload.notify_all_staff)
    db.refresh(cluster)
    return _build_detail(db, cluster)


@router.post("/{cluster_id}/incident/resolve", response_model=IssueClusterDetail)
def resolve_cluster_incident(
    cluster_id: uuid.UUID,
    payload: IncidentResolve,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Bulk-resolves every still-open ticket in the cluster with one shared
    reply, instead of the admin retyping the same resolution into each
    ticket individually."""
    cluster = _get_cluster_or_404(db, cluster_id)
    if cluster.incident_status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active incident to resolve")
    if not payload.resolution_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resolution text can't be empty")
    resolve_incident(db, cluster, payload.resolution_text.strip(), admin)
    db.refresh(cluster)
    return _build_detail(db, cluster)
