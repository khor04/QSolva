import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Notification, Ticket, User
from app.services import tickets as ticket_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["account"])


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_own_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Anonymizes the account rather than deleting the row: every ticket,
    message, and feedback entry references users(id), so overwriting
    name/email in place — instead of deleting — makes all of those resolve
    to "Deleted User" automatically, with no per-table cleanup. Ticket
    content, resolutions, embeddings, and cluster membership are all
    untouched; only the personal identity and notifications go."""
    # An admin's still-open work needs to go back to the queue — it can't
    # stay assigned to someone who no longer exists to act on it. A
    # resolved/closed ticket is left alone: it's finished, and reopening it
    # would erase the historical record of who handled it.
    if user.role == "admin":
        # Keyed on assigned_admin_id, not a specific status string like
        # "in_progress" — claim_ticket always pairs the two, but this stays
        # correct even if a ticket ever ends up assigned while not
        # in_progress for some other reason.
        still_assigned = (
            db.execute(
                select(Ticket).where(
                    Ticket.assigned_admin_id == user.id,
                    Ticket.status.notin_(["resolved", "closed"]),
                )
            )
            .scalars()
            .all()
        )
        for ticket in still_assigned:
            ticket_service.unassign_ticket(db, ticket)

    anonymized_email = f"deleted-{user.id}@deleted.qsolva.local"

    db.execute(delete(Notification).where(Notification.user_id == user.id))
    user.name = "Deleted User"
    user.email = anonymized_email
    user.deleted_at = datetime.now(timezone.utc)
    db.commit()

    if settings.supabase_service_role_key:
        try:
            httpx.put(
                f"{settings.supabase_url}/auth/v1/admin/users/{user.id}",
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                },
                json={
                    # auth.users.email — not public.users.email above — is
                    # what Supabase's signup uniqueness check is actually
                    # against. Without changing it here too, the real email
                    # stays permanently stuck on this banned account and can
                    # never be used to register again.
                    "email": anonymized_email,
                    "email_confirm": True,
                    # No true "permanent" ban value in the Admin API — a very
                    # long duration is the standard workaround. Not load-bearing
                    # for security: deleted_at (checked in deps.get_current_user)
                    # is what actually blocks API access, immediately, on our
                    # own terms; this just also stops them signing in at all.
                    "ban_duration": "876000h",
                },
                timeout=10,
            ).raise_for_status()
        except Exception:
            logger.exception("Failed to anonymize/ban Supabase auth user %s after account deletion", user.id)
