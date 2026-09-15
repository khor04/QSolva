"""Manually run the SLA-risk check on demand — the same function the
scheduler in app.main calls every hour. Useful for testing/demo rather than
waiting for the next scheduled run. Safe to rerun; only notifies once per
ticket.

Usage: python scripts/check_sla.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.sla import check_sla_risk

if __name__ == "__main__":
    flagged = check_sla_risk()
    print(f"Flagged {flagged} ticket(s) as at SLA risk.")
