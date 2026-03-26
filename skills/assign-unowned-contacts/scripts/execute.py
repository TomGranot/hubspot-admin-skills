# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Assign Unowned Contacts — Execute
Batch-assign all marketing contacts with no owner to a specified owner.

CONFIGURATION REQUIRED:
  Set TARGET_OWNER_ID below (or in .env as HUBSPOT_TARGET_OWNER_ID).
  Run before.py first to see available owner IDs.

Uses HubSpot batch update API with batches of 100.
Exports CSV audit trail of assigned contact IDs.
"""

import csv
import os
import time

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

# SET THIS to the owner ID you want to assign unowned contacts to.
# Run before.py to see available owner IDs, or check HubSpot Settings > Users.
TARGET_OWNER_ID = os.environ.get("HUBSPOT_TARGET_OWNER_ID", "")

SEARCH_URL = f"{BASE}/crm/v3/objects/contacts/search"
BATCH_SIZE = 100
MAX_RETRIES = 5
SAFETY_THRESHOLD = 50_000  # abort if more than this many contacts
PAGINATE_DELAY = 0.15      # seconds between paginated requests
BATCH_DELAY = 0.5          # seconds between batch operations
CSV_FILE = os.path.join(os.path.dirname(__file__), "execute_assign_unowned.csv")

# ── Helpers ──────────────────────────────────────────────────────

def search_all_ids(filters):
    """Collect all matching contact IDs via paginated search."""
    ids = []
    after = None
    while True:
        body = {
            "filterGroups": [{"filters": filters}],
            "properties": ["email", "hubspot_owner_id"],
            "limit": 100,
        }
        if after:
            body["after"] = after

        for attempt in range(MAX_RETRIES):
            resp = requests.post(SEARCH_URL, headers=HEADERS, json=body)
            if resp.status_code == 429:
                wait = min(10 * (attempt + 1), 30)
                print(f"      Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        else:
            resp.raise_for_status()

        data = resp.json()
        for r in data.get("results", []):
            ids.append(r["id"])
        after = data.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
        time.sleep(PAGINATE_DELAY)
    return ids


def batch_update(record_ids, properties):
    """Batch update contacts. Returns (success_count, failed_ids)."""
    update_url = f"{BASE}/crm/v3/objects/contacts/batch/update"
    success = 0
    failed = []
    total_batches = (len(record_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, len(record_ids), BATCH_SIZE):
        batch = record_ids[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        payload = {
            "inputs": [{"id": rid, "properties": properties} for rid in batch]
        }
        print(f"  Batch {batch_num}/{total_batches}: "
              f"assigning {len(batch)} contacts...", end=" ")

        for attempt in range(MAX_RETRIES):
            resp = requests.post(update_url, headers=HEADERS, json=payload)
            if resp.status_code == 429:
                wait = min(10 * (attempt + 1), 30)
                print(f"rate limited, waiting {wait}s...", end=" ")
                time.sleep(wait)
                continue
            break

        if resp.status_code in (200, 201):
            success += len(batch)
            print("OK")
        else:
            failed.extend(batch)
            print(f"FAILED ({resp.status_code}: {resp.text[:200]})")
        time.sleep(BATCH_DELAY)

    return success, failed


# ── Main ─────────────────────────────────────────────────────────

print("=" * 60)
print("EXECUTE: Assign Unowned Marketing Contacts")
print("=" * 60)
print()

# Validate owner ID
if not TARGET_OWNER_ID:
    print("ERROR: TARGET_OWNER_ID is not set.")
    print("  Set it in this script or as HUBSPOT_TARGET_OWNER_ID in .env")
    print("  Run before.py to see available owner IDs.")
    raise SystemExit(1)

# Verify the owner exists
print(f"Verifying owner ID: {TARGET_OWNER_ID}...")
owner_resp = requests.get(f"{BASE}/crm/v3/owners/{TARGET_OWNER_ID}", headers=HEADERS)
if owner_resp.status_code == 200:
    owner = owner_resp.json()
    name = f"{owner.get('firstName', '')} {owner.get('lastName', '')}".strip()
    email = owner.get("email", "N/A")
    print(f"  Owner: {name} ({email})")
else:
    print(f"  WARNING: Could not verify owner ID {TARGET_OWNER_ID} "
          f"(HTTP {owner_resp.status_code}). Proceeding anyway.")
print()

# Find unowned marketing contacts
print("Finding unowned marketing contacts...")
ids = search_all_ids([
    {"propertyName": "hubspot_owner_id", "operator": "NOT_HAS_PROPERTY"},
    {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
])
print(f"  Found {len(ids):,} unowned marketing contacts")
print()

if len(ids) > SAFETY_THRESHOLD:
    print(f"SAFETY: Found {len(ids):,} contacts — exceeds threshold "
          f"({SAFETY_THRESHOLD:,}). Aborting.")
    print("  Increase SAFETY_THRESHOLD if you are sure this is correct.")
    raise SystemExit(1)

if not ids:
    print("No unowned marketing contacts found. Nothing to do.")
    raise SystemExit(0)

# Batch assign
print(f"Assigning {len(ids):,} contacts to owner {TARGET_OWNER_ID}...")
success, failed = batch_update(ids, {"hubspot_owner_id": TARGET_OWNER_ID})

# ── CSV audit trail ──────────────────────────────────────────────
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["contact_id", "status"])
    writer.writeheader()
    for cid in ids:
        status = "failed" if cid in set(failed) else "assigned"
        writer.writerow({"contact_id": cid, "status": status})
print(f"\nAudit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
print()
print("=" * 60)
print("EXECUTION SUMMARY")
print("=" * 60)
print(f"  Target owner: {TARGET_OWNER_ID}")
print(f"  Contacts found:    {len(ids):,}")
print(f"  Successfully assigned: {success:,}")
print(f"  Failed:            {len(failed):,}")
print()
print("  Next step: Run after.py to verify all contacts now have an owner.")
print("=" * 60)
