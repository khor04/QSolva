"""Helpers for creating notifications. Callers add these to the same DB
session as the rest of their transaction and rely on that transaction's own
commit — this module never commits."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification, User


def _now() -> datetime:
    return datetime.now(timezone.utc)


def notify(
    db: Session,
    user_id: uuid.UUID,
    notification_type: str,
    ticket_id: uuid.UUID | None = None,
    message: str | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user_id, type=notification_type, ticket_id=ticket_id, message=message, is_read=False,
            created_at=_now(),
        )
    )


def notify_admins(
    db: Session,
    notification_type: str,
    ticket_id: uuid.UUID | None = None,
    exclude_user_id: uuid.UUID | None = None,
    message: str | None = None,
) -> None:
    admin_ids = db.execute(select(User.id).where(User.role == "admin")).scalars().all()
    for admin_id in admin_ids:
        if admin_id == exclude_user_id:
            continue
        notify(db, admin_id, notification_type, ticket_id, message=message)


def all_staff_ids(db: Session) -> list[uuid.UUID]:
    """Deleted accounts are excluded — their login is already revoked (see
    deps.get_current_user), so notifying them would just be a wasted row."""
    return list(db.execute(select(User.id).where(User.role == "staff", User.deleted_at.is_(None))).scalars().all())
