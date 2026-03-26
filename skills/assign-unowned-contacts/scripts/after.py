# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Assign Unowned Contacts — After State
Verify all marketing contacts now have an owner assigned.

Compares against the before-state baseline if available.
"""

import csv
import os

import requests
from dotenv import load_dotenv

# ── Configuration ────────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

SEARCH_URL = f"{BASE}/crm/v3/objects/contacts/search"
CSV_FILE = os.path.join(os.path.dirname(__file__), "after_assign_unowned.csv")

# Load before-state baseline
BEFORE_CSV = os.path.join(os.path.dirname(__file__), "before_assign_unowned.csv")
before_unowned = None
if os.path.exists(BEFORE_CSV):
    with open(BEFORE_CSV) as f:
        for row in csv.DictReader(f):
            if row["metric"] == "unowned_marketing_contacts":
                before_unowned = int(row["value"])

# ── Helpers ──────────────────────────────────────────────────────

def search_count(filters):
    resp = requests.post(SEARCH_URL, headers=HEADERS, json={
        "filterGroups": [{"filters": filters}],
        "limit": 1,
    })
    resp.raise_for_status()
    return resp.json().get("total", 0)


# ── Main ─────────────────────────────────────────────────────────

print("=" * 60)
print("AFTER STATE: Verify Marketing Contact Owner Assignment")
print("=" * 60)
print()

# Step 1 — unowned marketing contacts
print("Step 1: Marketing contacts without owner...")
remaining = search_count([
    {"propertyName": "hubspot_owner_id", "operator": "NOT_HAS_PROPERTY"},
    {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
])
print(f"  Unowned marketing contacts: {remaining}")
print()

# Step 2 — owned marketing contacts
print("Step 2: Marketing contacts with owner...")
owned = search_count([
    {"propertyName": "hubspot_owner_id", "operator": "HAS_PROPERTY"},
    {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
])
print(f"  Owned marketing contacts: {owned}")
print()

# ── CSV audit trail ──────────────────────────────────────────────
rows = [
    {"metric": "unowned_marketing_contacts", "value": remaining},
    {"metric": "owned_marketing_contacts", "value": owned},
]
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["metric", "value"])
    writer.writeheader()
    writer.writerows(rows)
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
print()
print("=" * 60)
print("AFTER STATE SUMMARY")
print("=" * 60)

if before_unowned is not None:
    assigned = before_unowned - remaining
    print(f"  Before: {before_unowned} unowned marketing contacts")
    print(f"  After:  {remaining} unowned marketing contacts")
    print(f"  Delta:  {assigned} contacts assigned")
else:
    print(f"  Unowned marketing contacts: {remaining}")
    print("  (Run before.py first to capture a baseline)")

print()
if remaining == 0:
    print("  SUCCESS — All marketing contacts now have an owner.")
elif before_unowned is not None and remaining < before_unowned:
    print(f"  PARTIAL — {remaining} marketing contacts still have no owner.")
    print("  New contacts may have arrived since the execute script ran.")
else:
    print("  NO CHANGE — Assignment may not have been applied yet.")
print("=" * 60)
