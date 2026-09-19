import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import AdminInviteCode, Ticket, User
from app.schemas import AdminInviteCodeCreate, AdminInviteCodeOut, AdminWorkload
from app.services.sla import SLA_THRESHOLD_DAYS

router = APIRouter(prefix="/admin", tags=["admin"])

# No 0/O or 1/I — both look alike when someone reads a code aloud or copies
# it off a screen.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate_code() -> str:
    groups = ["".join(secrets.choice(_CODE_ALPHABET) for _ in range(4)) for _ in range(2)]
    return "QS-" + "-".join(groups)


def _hash_code(code: str) -> str:
    # Must match the Postgres trigger's md5(text) exactly (see alembic 0008)
    # — same algorithm, same lowercase-hex encoding.
    return hashlib.md5(code.encode()).hexdigest()


@router.get("/workload", response_model=list[AdminWorkload])
def get_workload(_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Per-admin load so someone deciding what to claim, or who to hand a
    ticket to, can see who is carrying what. Outer join so an admin with
    nothing assigned still shows up (as idle) rather than vanishing."""
    overdue_cutoff = datetime.now(timezone.utc) - timedelta(days=SLA_THRESHOLD_DAYS)
    rows = db.execute(
        select(
            User.id,
            User.name,
            func.count(Ticket.id),
            func.count(Ticket.id).filter(Ticket.priority.in_(["high", "critical"])),
            func.count(Ticket.id).filter(Ticket.created_at < overdue_cutoff),
        )
        .select_from(User)
        .outerjoin(
            Ticket,
            and_(
                Ticket.assigned_admin_id == User.id,
                Ticket.status.in_(["open", "in_progress", "escalated"]),
            ),
        )
        .where(User.role == "admin", User.deleted_at.is_(None))
        .group_by(User.id, User.name)
        .order_by(User.name)
    ).all()
    return [
        AdminWorkload(
            id=id_, name=name, active_tickets=active, high_critical_tickets=high, overdue_tickets=overdue
        )
        for id_, name, active, high, overdue in rows
    ]


@router.post("/invite-codes", response_model=AdminInviteCodeOut)
def create_invite_code(
    payload: AdminInviteCodeCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Any existing admin can mint a code for the next one — this app
    doesn't distinguish an HOD from any other admin. The raw code is
    returned only in this response; only its hash is ever persisted."""
    code = _generate_code()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days is not None
        else None
    )
    db.add(
        AdminInviteCode(
            code_hash=_hash_code(code),
            created_by=admin.id,
            expires_at=expires_at,
            max_uses=payload.max_uses,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return AdminInviteCodeOut(code=code, expires_at=expires_at, max_uses=payload.max_uses)
