"""tickets.already_tried_cluster_id: which recurring-issue cluster's Help
Center answer (if any) the reporter already tried and rejected before filing
this ticket — set from NewTicket.tsx's "Doesn't fix it — submit anyway" flow
(see routers/tickets.create_ticket). Lets the RAG stage exclude that cluster's
evidence so it doesn't just resurface the same already-rejected fix as a
fresh suggestion, and lets the ticket detail page warn the admin not to
resend it (see services/tickets._run_rag_stage, TicketDetail.tsx).

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "alter table tickets add column already_tried_cluster_id uuid references issue_clusters(id)"
    )


def downgrade() -> None:
    op.execute("alter table tickets drop column already_tried_cluster_id")
