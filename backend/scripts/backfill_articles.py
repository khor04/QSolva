"""Repair utility: drafts a Help Center article for any cluster that has
enough evidence but never got one — typically because a Gemini 429 hit the
one-shot _refresh_article call at the exact moment its member count crossed
a threshold, with no retry until the next threshold. Safe to rerun; only
touches clusters with article_question still null.

Usage: python scripts/backfill_articles.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal
from app.models import IssueCluster
from app.services.issues import MIN_MEMBERS_FOR_SUMMARY, _refresh_article, gather_evidence


async def main():
    db = SessionLocal()
    try:
        clusters = (
            db.query(IssueCluster)
            .filter(IssueCluster.member_count >= MIN_MEMBERS_FOR_SUMMARY, IssueCluster.article_question.is_(None))
            .all()
        )
        if not clusters:
            print("Nothing to backfill — every eligible cluster already has a draft.")
            return

        print(f"Checking {len(clusters)} cluster(s) missing a draft article...")
        drafted = 0
        for cluster in clusters:
            evidence = gather_evidence(db, cluster.id)
            if evidence.best_resolution is None:
                print(f"  skip {cluster.label!r} — no usable resolution evidence yet")
                continue
            try:
                await _refresh_article(db, cluster)
                db.commit()
                if cluster.article_question:
                    drafted += 1
                    print(f"  drafted {cluster.label!r}")
                else:
                    print(f"  {cluster.label!r} — still no draft after refresh (unexpected)")
            except Exception as exc:
                db.rollback()
                print(f"  FAILED on {cluster.label!r}: {exc}")

        print(f"\nDone. {drafted}/{len(clusters)} cluster(s) drafted.")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
