"""Dev utility: seed realistic tickets so the AI Resolution Assistant has
historical data to retrieve from (the cold-start problem), and so the
Recurring Issues feature has real recurring themes to cluster instead of an
empty /issues page. Resolved tickets get a real Gemini embedding so future
similarity search and clustering can actually find them.

Safe-ish to rerun, but not idempotent — reruns will add duplicate tickets.
Run once, then `python scripts/backfill_clusters.py` to cluster everything.

Usage: python scripts/seed_tickets.py
"""
import asyncio
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import AiSuggestion, Feedback, Ticket, TicketEmbedding, TicketMessage, User
from app.services import ai

random.seed(42)  # reproducible demo data


def now():
    return datetime.now(timezone.utc)


SEED_TICKETS = [
    {
        "title": "VPN connection keeps timing out",
        "description": "Since this morning I can't stay connected to the company VPN. It connects for a few seconds and then disconnects, over and over.",
        "category": "network",
        "priority": "high",
        "priority_confidence": 0.91,
        "status": "resolved",
        "resolution": "Cleared the saved VPN credentials and restarted the VPN client. Reconnected successfully after re-entering credentials.",
        "days_ago": 6,
    },
    {
        "title": "VPN disconnects every few minutes after Windows update",
        "description": "After last week's Windows update, my VPN drops every 3-5 minutes and I have to manually reconnect each time.",
        "category": "network",
        "priority": "high",
        "priority_confidence": 0.88,
        "status": "resolved",
        "resolution": "Removed and reinstalled the VPN adapter, then reset network settings. Issue resolved after the adapter reinstall.",
        "days_ago": 4,
    },
    {
        "title": "VPN authentication failing intermittently",
        "description": "VPN login works about half the time, other times it just says authentication failed and I have to retry several times.",
        "category": "network",
        "priority": "medium",
        "priority_confidence": 0.82,
        "status": "closed",
        "resolution": "Cleared cached VPN credentials and had the user re-authenticate. Recommended enabling 'remember credentials' to avoid repeated prompts.",
        "days_ago": 2,
    },
    {
        "title": "Cannot access shared email inbox",
        "description": "I used to have access to the support@company.com shared inbox in Outlook but it disappeared from my account this week.",
        "category": "email_account",
        "priority": "medium",
        "priority_confidence": 0.76,
        "status": "resolved",
        "resolution": "Reset the user's Outlook profile and re-added the shared mailbox permissions in the admin console.",
        "days_ago": 3,
    },
    {
        "title": "Laptop overheating and shutting down randomly",
        "description": "My laptop gets very hot after about 20 minutes of use and then shuts off without warning. Started happening this week.",
        "category": "hardware",
        "priority": "high",
        "priority_confidence": 0.79,
        "status": "open",
        "resolution": None,
        "days_ago": 0,
    },
]


# Recurring-issue themes for the Recurring Issues (clustering) demo. Each
# theme cycles through a small pool of paraphrased title/description pairs
# (realistic — many employees report the same problem in similar words) and
# a small pool of plausible resolutions. prev_week/this_week counts are
# picked to produce meaningful, explainable growth percentages.
THEMES = [
    {
        "name": "VPN / Network",
        "category": "network",
        "priority": "high",
        "prev_week_count": 5,
        "this_week_count": 18,
        "tickets": [
            ("VPN connection times out", "My VPN connects for a few seconds then disconnects, over and over, since this morning."),
            ("VPN disconnects every few minutes", "The VPN drops every 3-5 minutes and I have to manually reconnect each time."),
            ("VPN authentication failing intermittently", "VPN login works about half the time, other times it says authentication failed."),
            ("Cannot connect to VPN at all", "I get a timeout error every time I try to connect to the VPN this morning."),
            ("VPN drops when switching WiFi networks", "Every time I move between office WiFi and my hotspot the VPN disconnects and won't reconnect."),
            ("VPN client crashes on launch", "The VPN client crashes immediately when I try to open it, worked fine yesterday."),
            ("Slow VPN causing remote desktop to lag", "My VPN connection is extremely slow today, remote desktop sessions keep freezing."),
            ("VPN keeps asking to reauthenticate", "I get logged out of the VPN every 10 minutes and have to re-enter my credentials."),
        ],
        "resolutions": [
            "Cleared the saved VPN credentials and restarted the VPN client. Reconnected successfully after re-entering credentials.",
            "Removed and reinstalled the VPN adapter, then reset network settings. Issue resolved after the adapter reinstall.",
            "Cleared cached VPN credentials and had the user re-authenticate. Recommended enabling 'remember credentials'.",
            "Updated the VPN client to the latest version, which fixed the reconnect loop.",
        ],
    },
    {
        "name": "Microsoft 365 Login",
        "category": "access",
        "priority": "medium",
        "prev_week_count": 4,
        "this_week_count": 11,
        "tickets": [
            ("Cannot sign in to Microsoft 365", "I keep getting 'Your account or password is incorrect' in Outlook and Teams even though the password is right."),
            ("Microsoft 365 MFA prompt not arriving", "The Microsoft Authenticator push notification never arrives when I try to sign into M365."),
            ("Teams keeps signing me out", "Microsoft Teams logs me out every hour and I have to sign back into all my M365 apps."),
            ("Outlook stuck on 'need password' loop", "Outlook keeps asking for my password even after I enter it correctly, it just loops back."),
            ("Locked out of Microsoft 365 account", "After a few failed sign-in attempts this morning my Microsoft 365 account is now locked."),
            ("Sign-in error on Microsoft 365 portal", "Getting a sign-in error trying to reach the Microsoft 365 portal since this morning."),
        ],
        "resolutions": [
            "Reset the user's Microsoft 365 password and cleared cached credentials in Windows Credential Manager.",
            "Re-registered the user's device with Microsoft Authenticator after an MFA sync issue.",
            "Unlocked the Microsoft 365 account in the admin center after verifying identity.",
        ],
    },
    {
        "name": "Printer Connectivity",
        "category": "hardware",
        "priority": "low",
        "prev_week_count": 5,
        "this_week_count": 7,
        "tickets": [
            ("Office printer not responding", "The printer on the 3rd floor isn't responding to any print jobs since this morning."),
            ("Print jobs stuck in queue", "My documents are stuck in the print queue and never actually print."),
            ("Cannot connect to network printer", "My laptop can't find the office network printer anymore, worked fine last week."),
            ("Printer showing offline", "The shared printer shows as offline on my computer even though it's powered on."),
        ],
        "resolutions": [
            "Restarted the print spooler service and cleared the stuck print queue.",
            "Reinstalled the network printer driver and reconnected to the shared printer.",
            "Power-cycled the printer and reset its network connection; back online after restart.",
        ],
    },
    {
        "name": "Password & Access Requests",
        "category": "access",
        "priority": "medium",
        "prev_week_count": 3,
        "this_week_count": 10,
        "tickets": [
            ("Need access to shared finance drive", "I was just moved to the Finance team and need access to the shared Finance drive."),
            ("Password reset link not working", "The password reset email link I received says it's expired even though I just requested it."),
            ("Locked out of my account after failed attempts", "I mistyped my password a few times and now my account is locked."),
            ("New starter needs system access", "We have a new starter joining Monday and they need access set up for the shared systems."),
            ("Cannot access HR portal", "I no longer have access to the HR portal since the recent system change."),
        ],
        "resolutions": [
            "Granted the requested folder permissions after manager approval.",
            "Manually unlocked the account and had the user reset their password.",
            "Provisioned system access for the new starter ahead of their start date.",
        ],
    },
    {
        "name": "Software Installation",
        "category": "software",
        "priority": "low",
        "prev_week_count": 3,
        "this_week_count": 8,
        "tickets": [
            ("Need Adobe Acrobat installed", "I need Adobe Acrobat Pro installed on my laptop for a client project starting this week."),
            ("Software update failing to install", "The latest software update keeps failing partway through installation with an error."),
            ("Cannot install approved software from portal", "The company software portal shows an error whenever I try to install anything."),
            ("Need Zoom installed for new laptop", "My new laptop doesn't have Zoom installed and I have a client call this afternoon."),
        ],
        "resolutions": [
            "Installed the requested software via the IT deployment tool.",
            "Cleared the software installer cache and reran the update, which completed successfully.",
            "Fixed a permissions issue in the software portal that was blocking installs.",
        ],
    },
]


def spread_timestamps(count: int, min_days_ago: float, max_days_ago: float) -> list[datetime]:
    times = [now() - timedelta(days=random.uniform(min_days_ago, max_days_ago)) for _ in range(count)]
    return sorted(times)


async def seed_original(db, staff: User, admin: User) -> None:
    for spec in SEED_TICKETS:
        if db.execute(select(Ticket).where(Ticket.title == spec["title"])).scalar_one_or_none() is not None:
            print(f"Skipped (already exists): {spec['title']}")
            continue

        created_at = now() - timedelta(days=spec["days_ago"])
        ticket = Ticket(
            id=uuid.uuid4(),
            staff_id=staff.id,
            assigned_admin_id=admin.id if spec["status"] != "open" else None,
            title=spec["title"],
            description=spec["description"],
            category=spec["category"],
            status=spec["status"],
            priority=spec["priority"],
            priority_confidence=spec["priority_confidence"],
            priority_source="ai",
            ai_priority_status="success",
            # seed_original never creates an AiSuggestion (see below), so
            # there's never a suggestion to show regardless of resolution.
            ai_rag_status="no_match",
            created_at=created_at,
            updated_at=created_at,
            resolved_at=created_at if spec["status"] in ("resolved", "closed") else None,
            closed_at=created_at if spec["status"] == "closed" else None,
        )
        db.add(ticket)
        db.flush()

        if spec["resolution"]:
            db.add(TicketMessage(ticket_id=ticket.id, sender_id=admin.id, body=spec["resolution"], created_at=created_at))
            embedding = await ai.embed_text(f"{ticket.title}\n{ticket.description}")
            db.add(
                TicketEmbedding(
                    ticket_id=ticket.id, embedding=embedding, model_name=settings.embedding_model, updated_at=created_at
                )
            )
            print(f"Seeded (resolved, embedded): {ticket.title}")
        else:
            print(f"Seeded (open, no embedding yet): {ticket.title}")

    db.commit()


async def seed_themes(db, staff: User, admin: User) -> None:
    for theme in THEMES:
        prev_times = spread_timestamps(theme["prev_week_count"], 7, 13.9)
        this_times = spread_timestamps(theme["this_week_count"], 0, 6.9)
        all_times = prev_times + this_times

        print(f"\n{theme['name']}: seeding {len(all_times)} tickets...")
        for i, created_at in enumerate(all_times):
            title, description = theme["tickets"][i % len(theme["tickets"])]
            # The most recent ~20% are still being worked (realistic aging: a
            # fresh spike hasn't all been resolved yet).
            still_open = i >= len(all_times) - max(1, len(all_times) // 5)
            status = "open" if still_open else random.choice(["resolved", "resolved", "resolved", "closed"])

            ticket = Ticket(
                id=uuid.uuid4(),
                staff_id=staff.id,
                assigned_admin_id=admin.id if status != "open" else None,
                title=title,
                description=description,
                category=theme["category"],
                status=status,
                priority=theme["priority"],
                priority_confidence=round(random.uniform(0.75, 0.95), 2),
                priority_source="ai",
                ai_priority_status="success",
                # A suggestion is only ever added below for resolved/closed
                # tickets — "still open" ones never get one.
                ai_rag_status="success" if status in ("resolved", "closed") else "no_match",
                created_at=created_at,
                updated_at=created_at,
                resolved_at=created_at if status in ("resolved", "closed") else None,
                closed_at=created_at if status == "closed" else None,
            )
            db.add(ticket)
            db.flush()

            try:
                embedding = await ai.embed_text(f"{ticket.title}\n{ticket.description}")
            except Exception as exc:
                print(f"  [{i + 1}/{len(all_times)}] embedding FAILED for {title!r}: {exc}")
                ticket.ai_rag_status = "failed"
                db.commit()
                continue

            db.add(
                TicketEmbedding(
                    ticket_id=ticket.id, embedding=embedding, model_name=settings.embedding_model, updated_at=created_at
                )
            )

            if status in ("resolved", "closed"):
                resolution_text = random.choice(theme["resolutions"])
                db.add(TicketMessage(ticket_id=ticket.id, sender_id=admin.id, body=resolution_text, created_at=created_at))

                # Mostly successful outcomes, with occasional partial/failed
                # feedback so success_rate isn't a flat 100%.
                outcome = random.choices(
                    ["solved", "partially_solved", "did_not_solve"],
                    weights=[0.82, 0.1, 0.08],
                )[0]
                suggestion = AiSuggestion(
                    ticket_id=ticket.id,
                    resolution_text=resolution_text,
                    confidence=round(random.uniform(0.85, 0.97), 2),
                    state="accepted" if outcome == "solved" else "rejected",
                    evidence=[],
                    created_at=created_at,
                )
                db.add(suggestion)
                db.flush()
                db.add(
                    Feedback(
                        ai_suggestion_id=suggestion.id,
                        ticket_id=ticket.id,
                        staff_id=staff.id,
                        outcome=outcome,
                        created_at=created_at,
                    )
                )

            db.commit()
            print(f"  [{i + 1}/{len(all_times)}] {title!r} ({status})")


async def main():
    db = SessionLocal()
    try:
        staff = db.execute(select(User).where(User.role == "staff")).scalars().first()
        admin = db.execute(select(User).where(User.role == "admin")).scalars().first()
        if staff is None or admin is None:
            print("Need at least one staff and one admin user in public.users first.")
            return

        await seed_original(db, staff, admin)
        await seed_themes(db, staff, admin)

        print("\nDone. Now run: python scripts/backfill_clusters.py")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
