"""External delivery for admin-actionable alerts, over Slack. Deliberately
narrow: only critical/high-priority tickets, SLA risk, admin-directed
escalations, and new incidents page out here (see each call site) — every
other notification stays in-app only (app.services.notifications), since
paging on every event would be noise, not signal.

Best-effort and fire-and-forget: a failed or unconfigured webhook never
raises, since the in-app notification this accompanies is already the
source of truth and shouldn't be undone by a Slack hiccup.
"""

import logging
import uuid

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _ticket_link(ticket_id: uuid.UUID | None) -> str:
    if ticket_id is None or not settings.app_base_url:
        return ""
    return f"\n{settings.app_base_url.rstrip('/')}/tickets/{ticket_id}"


def send_admin_alert(text: str, ticket_id: uuid.UUID | None = None) -> None:
    if not settings.admin_alert_slack_webhook_url:
        return
    try:
        httpx.post(
            settings.admin_alert_slack_webhook_url,
            json={"text": text + _ticket_link(ticket_id)},
            timeout=10,
        )
    except httpx.HTTPError:
        logger.warning("Failed to send Slack admin alert")
