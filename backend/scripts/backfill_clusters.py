"""One-time (but safe to rerun) utility: assigns issue clusters to any
ticket that already has an embedding but no cluster_id yet — e.g. tickets
seeded before the Recurring Issues feature existed. Reuses each ticket's
existing embedding; does not call the embedding API again.

Processes tickets oldest-first so clusters form in the same chronological
order they would have in production.

Usage: python scripts/backfill_clusters.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Ticket, TicketEmbedding
from app.services.issues import assign_cluster


async def main():
    db = SessionLocal()
    try:
        rows = db.execute(
            select(Ticket, TicketEmbedding)
            .join(TicketEmbedding, TicketEmbedding.ticket_id == Ticket.id)
            .where(Ticket.cluster_id.is_(None))
            .order_by(Ticket.created_at)
        ).all()

        if not rows:
            print("Nothing to backfill — every embedded ticket already has a cluster.")
            return

        print(f"Backfilling clusters for {len(rows)} ticket(s)...")
        done = 0
        for ticket, embedding_row in rows:
            try:
                cluster = await assign_cluster(db, ticket, embedding_row.embedding)
                db.commit()
                done += 1
                print(f"  [{done}/{len(rows)}] {ticket.title!r} -> cluster {cluster.id} (members={cluster.member_count})")
            except Exception as exc:
                db.rollback()
                print(f"  FAILED on {ticket.title!r}: {exc}")

        print(f"\nDone. {done}/{len(rows)} ticket(s) clustered.")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
