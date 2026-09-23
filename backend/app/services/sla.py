"""Automated SLA-risk detection: periodically flags tickets that have passed
the deadline for whatever they're currently waiting on, notifying the assigned
admin (or all admins if unassigned). The deadlines come from
services/sla_policy — the same ones the staff page and the admin queue show —
so "overdue" means the same thing everywhere.

A ticket is always waiting on exactly one thing: a first response until an
admin claims/replies, then a resolution. That's the deadline checked here, in
overdue_clause below, and in the frontend's lib/sla.ts.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select

from app.db import SessionLocal
from app.models import Notification, Ticket
from app.services.alerts import send_admin_alert
from app.services.notifications import notify, notify_admins

logger = logging.getLogger(__name__)

# Tickets an admin is still on the hook for. Resolved is waiting on the staff
# member to confirm, so it can't be "overdue" on the admin's side.
ACTIVE_STATUSES = ("open", "in_progress", "escalated")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def overdue_clause(now: datetime):
    """SQL condition: the ticket's *current* deadline (response_due_at until
    an admin responds, then resolution_due_at — both stored, see models.Ticket)
    has passed. Callers add their own status filter (ACTIVE_STATUSES)."""
    return or_(
        and_(Ticket.first_response_at.is_(None), Ticket.response_due_at < now),
        and_(Ticket.first_response_at.is_not(None), Ticket.resolution_due_at < now),
    )


def check_sla_risk() -> int:
    """Notifies once per at-risk ticket per deadline (response, then
    resolution) — safe to call repeatedly (e.g. on a schedule) since it skips
    tickets that already have a matching sla_risk notification on record.
    Returns the number of tickets newly flagged."""
    db = SessionLocal()
    try:
        at_risk = (
            db.execute(select(Ticket).where(Ticket.status.in_(ACTIVE_STATUSES), overdue_clause(_now())))
            .scalars()
            .all()
        )

        flagged = 0
        for ticket in at_risk:
            # The notification's message records which deadline was missed, so
            # missing the response deadline doesn't suppress a later alert
            # for missing the resolution one.
            kind = "response" if ticket.first_response_at is None else "resolution"
            already_notified = db.execute(
                select(Notification.id)
                .where(
                    Notification.ticket_id == ticket.id,
                    Notification.type == "sla_risk",
                    Notification.message == kind,
                )
                .limit(1)
            ).scalar_one_or_none()
            if already_notified is not None:
                continue

            if ticket.assigned_admin_id:
                notify(db, ticket.assigned_admin_id, "sla_risk", ticket.id, message=kind)
            else:
                notify_admins(db, "sla_risk", ticket.id, message=kind)
            deadline = "first response" if kind == "response" else "resolution"
            send_admin_alert(f"🟡 SLA risk — {ticket.title} is past its {deadline} deadline", ticket.id)
            flagged += 1

        db.commit()
        if flagged:
            logger.info("SLA risk check: flagged %d ticket(s)", flagged)
        return flagged
    finally:
        db.close()
