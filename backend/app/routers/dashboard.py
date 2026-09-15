from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import AiSuggestion, IssueCluster, Ticket, User
from app.routers.issues import _pct_change, _severity, _week_counts
from app.schemas import (
    AiPerformance,
    DashboardEmergingIssue,
    DashboardStats,
    DashboardTrendPoint,
    PriorityDistribution,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

OVERDUE_MS_DAYS = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/stats", response_model=DashboardStats)
def get_stats(_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    total = db.execute(select(func.count()).select_from(Ticket)).scalar_one()
    open_count = db.execute(
        select(func.count()).select_from(Ticket).where(Ticket.status.in_(["open", "in_progress", "escalated"]))
    ).scalar_one()

    overdue_cutoff = _now() - timedelta(days=OVERDUE_MS_DAYS)
    overdue_count = db.execute(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.status.in_(["open", "in_progress", "escalated"]), Ticket.created_at < overdue_cutoff)
    ).scalar_one()

    resolved_count = db.execute(
        select(func.count()).select_from(Ticket).where(Ticket.status == "resolved")
    ).scalar_one()
    closed_count = db.execute(
        select(func.count()).select_from(Ticket).where(Ticket.status == "closed")
    ).scalar_one()

    recurring_issues_count = db.execute(
        select(func.count()).select_from(IssueCluster).where(IssueCluster.member_count >= 2)
    ).scalar_one()

    priority_rows = db.execute(select(Ticket.priority, func.count()).group_by(Ticket.priority)).all()
    priority_counts = {priority: count for priority, count in priority_rows}
    priority_distribution = PriorityDistribution(
        critical=priority_counts.get("critical", 0),
        high=priority_counts.get("high", 0),
        medium=priority_counts.get("medium", 0),
        low=priority_counts.get("low", 0),
    )

    since = _now() - timedelta(days=14)
    trend_rows = db.execute(
        select(func.date(Ticket.created_at), func.count())
        .where(Ticket.created_at >= since)
        .group_by(func.date(Ticket.created_at))
        .order_by(func.date(Ticket.created_at))
    ).all()
    volume_trend = [DashboardTrendPoint(date=str(day), count=count) for day, count in trend_rows]

    clusters = (
        db.execute(select(IssueCluster).where(IssueCluster.member_count >= 2)).scalars().all()
    )
    emerging = []
    for cluster in clusters:
        this_week, prev_week = _week_counts(db, cluster.id)
        pct = _pct_change(this_week, prev_week)
        emerging.append(
            DashboardEmergingIssue(
                id=cluster.id,
                label=cluster.label,
                tickets_this_week=this_week,
                pct_change=pct,
                severity=_severity(this_week, pct),
            )
        )
    emerging.sort(key=lambda e: e.tickets_this_week, reverse=True)
    emerging_issues = emerging[:3]

    accepted = db.execute(
        select(func.count()).select_from(AiSuggestion).where(AiSuggestion.state == "accepted")
    ).scalar_one()
    rejected = db.execute(
        select(func.count()).select_from(AiSuggestion).where(AiSuggestion.state == "rejected")
    ).scalar_one()
    acceptance_rate = accepted / (accepted + rejected) if (accepted + rejected) else None

    # How often the RAG pipeline actually finds enough similar history to
    # produce a suggestion, out of tickets where RAG ran to completion —
    # excluding ones still pending or that failed outright, since those
    # never got a fair shot at producing one either way.
    rag_completed = db.execute(
        select(func.count()).select_from(Ticket).where(Ticket.ai_rag_status.in_(["success", "no_match"]))
    ).scalar_one()
    rag_success = db.execute(
        select(func.count()).select_from(Ticket).where(Ticket.ai_rag_status == "success")
    ).scalar_one()
    coverage_rate = (rag_success / rag_completed) if rag_completed else None

    # Tickets fully self-served: closed without an admin ever being assigned
    # to them at all — the AI Resolution Assistant's core value proposition.
    deflected = db.execute(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.status == "closed", Ticket.assigned_admin_id.is_(None))
    ).scalar_one()
    deflection_rate = (deflected / total) if total else None

    return DashboardStats(
        total_tickets=total,
        open_tickets=open_count,
        overdue_tickets=overdue_count,
        resolved_tickets=resolved_count,
        closed_tickets=closed_count,
        recurring_issues_count=recurring_issues_count,
        priority_distribution=priority_distribution,
        volume_trend=volume_trend,
        emerging_issues=emerging_issues,
        ai_performance=AiPerformance(
            acceptance_rate=acceptance_rate,
            coverage_rate=coverage_rate,
            deflection_rate=deflection_rate,
        ),
    )
