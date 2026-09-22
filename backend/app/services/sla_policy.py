"""The one definition of QSolva's SLA targets, and the due times derived from
them. Kept free of DB/model imports — Ticket.response_due_at/resolution_due_at
are plain stored columns (see routers/tickets.py and services/tickets.py,
which call compute_due_dates on creation and whenever priority changes), not
computed on read, because the business-hours clock below can't be expressed
as a SQL expression the way a flat "created_at + N days" could.

Two clocks, chosen by priority:
  - Critical/High: a department-down issue doesn't wait for business hours,
    so these run 24/7 — nights and weekends count.
  - Medium/Low: paused outside business hours, so staff going home for the
    weekend doesn't rack up hours against an SLA nobody could act on.

Two separate promises per priority regardless of clock: "we'll respond" (an
admin claims or replies) and "we'll resolve". Both run from the ticket's
creation time.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings

BUSINESS_TZ = ZoneInfo(settings.business_timezone)
BUSINESS_START_HOUR = settings.business_hours_start
BUSINESS_END_HOUR = settings.business_hours_end
BUSINESS_DAY_HOURS = BUSINESS_END_HOUR - BUSINESS_START_HOUR
# Mon-Fri: Python's Monday=0 .. Sunday=6.
BUSINESS_WEEKDAYS = range(0, 5)

# Safety cap on how many business-day windows add_business_time will walk
# through — a target this long would be a policy bug, not a real deadline.
_MAX_BUSINESS_DAYS = 60


@dataclass(frozen=True)
class SlaTargets:
    response: timedelta
    resolution: timedelta


# response/resolution values are read differently depending on the priority's
# clock (see CLOCK_FOR_PRIORITY): elapsed wall-clock time for critical/high,
# elapsed *business-hours* time for medium/low. Adjust freely — everything
# downstream (staff page, admin queue, dashboard counts, SLA-risk job) reads
# from response_due_at/resolution_due_at, not these constants directly.
SLA_POLICY: dict[str, SlaTargets] = {
    "critical": SlaTargets(response=timedelta(minutes=30), resolution=timedelta(hours=4)),
    "high": SlaTargets(response=timedelta(hours=2), resolution=timedelta(hours=8)),
    "medium": SlaTargets(response=timedelta(hours=4), resolution=timedelta(hours=2 * BUSINESS_DAY_HOURS)),
    "low": SlaTargets(response=timedelta(hours=BUSINESS_DAY_HOURS), resolution=timedelta(hours=4 * BUSINESS_DAY_HOURS)),
}

CLOCK_FOR_PRIORITY: dict[str, str] = {
    "critical": "calendar",
    "high": "calendar",
    "medium": "business",
    "low": "business",
}


def _add_business_time(start: datetime, duration: timedelta) -> datetime:
    """Walks `start` forward by `duration` of business-hours time, pausing
    outside BUSINESS_START_HOUR-BUSINESS_END_HOUR and on weekends. Naive
    about DST transitions that fall inside the business window (rare — most
    zones transition around 2am) and about holidays, which aren't modelled.
    """
    current = start.astimezone(BUSINESS_TZ)
    remaining = duration
    for _ in range(_MAX_BUSINESS_DAYS):
        day_start = current.replace(hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0)
        day_end = current.replace(hour=BUSINESS_END_HOUR, minute=0, second=0, microsecond=0)

        if current.weekday() not in BUSINESS_WEEKDAYS or current >= day_end:
            current = (current + timedelta(days=1)).replace(
                hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0
            )
            continue
        if current < day_start:
            current = day_start
            continue

        available_today = day_end - current
        if remaining <= available_today:
            return (current + remaining).astimezone(timezone.utc)
        remaining -= available_today
        current = (current + timedelta(days=1)).replace(hour=BUSINESS_START_HOUR, minute=0, second=0, microsecond=0)

    # Reaching here means a target longer than _MAX_BUSINESS_DAYS worth of
    # business time — treat as a policy misconfiguration rather than loop.
    raise ValueError(f"SLA target too long to resolve in business hours: {duration}")


def compute_due_dates(created_at: datetime, priority: str) -> tuple[datetime, datetime]:
    """Returns (response_due_at, resolution_due_at) for a ticket created at
    `created_at` with the given priority. Called whenever a ticket is created
    or its priority changes (AI classification or an admin override) — see
    services/tickets.py and routers/tickets.py — since the due dates are
    stored, not computed on read."""
    targets = SLA_POLICY[priority]
    if CLOCK_FOR_PRIORITY[priority] == "calendar":
        return (
            created_at.astimezone(timezone.utc) + targets.response,
            created_at.astimezone(timezone.utc) + targets.resolution,
        )
    return (
        _add_business_time(created_at, targets.response),
        _add_business_time(created_at, targets.resolution),
    )
