import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Notification, Ticket, User
from app.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_out(notification: Notification, ticket_title: str | None) -> NotificationOut:
    return NotificationOut(
        id=notification.id,
        type=notification.type,
        ticket_id=notification.ticket_id,
        ticket_title=ticket_title,
        message=notification.message,
        is_read=notification.is_read,
        created_at=notification.created_at,
    )


@router.get("", response_model=list[NotificationOut])
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Notification, Ticket.title)
        .join(Ticket, Ticket.id == Notification.ticket_id, isouter=True)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    ).all()
    return [_to_out(notification, title) for notification, title in rows]


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    title = db.get(Ticket, notification.ticket_id).title if notification.ticket_id else None
    return _to_out(notification, title)


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
