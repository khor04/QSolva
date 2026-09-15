"""Automated SLA-risk detection: periodically flags tickets that have sat
open too long without resolution, notifying the assigned admin (or all
admins if unassigned) — the proactive, notification-based counterpart to
the "Overdue" badge already shown in the admin queue. Uses the same 5-day
threshold rather than introducing a second, separately-tuned definition.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Notification, Ticket
from app.services.notifications import notify, notify_admins

logger = logging.getLogger(__name__)

SLA_THRESHOLD_DAYS = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def check_sla_risk() -> int:
    """Notifies once per at-risk ticket — safe to call repeatedly (e.g. on a
    schedule) since it skips tickets that already have an sla_risk
    notification on record. Returns the number of tickets newly flagged."""
    db = SessionLocal()
    try:
        cutoff = _now() - timedelta(days=SLA_THRESHOLD_DAYS)
        at_risk = (
            db.execute(
                select(Ticket).where(
                    Ticket.status.in_(["open", "in_progress", "escalated"]),
                    Ticket.created_at < cutoff,
                )
            )
            .scalars()
            .all()
        )

        flagged = 0
        for ticket in at_risk:
            already_notified = db.execute(
                select(Notification.id)
                .where(Notification.ticket_id == ticket.id, Notification.type == "sla_risk")
                .limit(1)
            ).scalar_one_or_none()
            if already_notified is not None:
                continue

            if ticket.assigned_admin_id:
                notify(db, ticket.assigned_admin_id, "sla_risk", ticket.id)
            else:
                notify_admins(db, "sla_risk", ticket.id)
            flagged += 1

        db.commit()
        if flagged:
            logger.info("SLA risk check: flagged %d ticket(s)", flagged)
        return flagged
    finally:
        db.close()
