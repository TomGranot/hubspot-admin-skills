# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Fix Lifecycle Stages — Execute
Move all contacts and companies in disallowed lifecycle stages to Lead.

Disallowed: Subscriber, Other, Evangelist, (empty)
Target: Lead

IMPORTANT: HubSpot lifecycle stages are forward-only. To move a record
from a "later" stage to an "earlier" stage (or from empty), you must:
  1. CLEAR the lifecycle stage property (set to empty string)
  2. SET it to the desired value
This script handles the clear-then-set pattern automatically.

Uses HubSpot batch update API with batches of 100.
Exports CSV audit trail of all changes.
"""

import csv
import os
import time

import requests
from dotenv import load_dotenv

# ── Configuration ────────────────────────────────────────────────
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

DISALLOWED_STAGES = ["subscriber", "other", "evangelist"]
BATCH_SIZE = 100
MAX_RETRIES = 5
SAFETY_THRESHOLD = 50_000  # abort if total exceeds this
PAGINATE_DELAY = 0.15      # seconds between paginated requests
BATCH_DELAY = 0.5          # seconds between batch operations
CSV_FILE = os.path.join("data", "audit-logs", "execute_fix_lifecycle.csv")

# ── Helpers ──────────────────────────────────────────────────────

def search_all_ids(object_type, filters):
    """Search and collect ALL record IDs matching filters.
    Handles the 10K HubSpot search pagination limit.
    """
    ids = []
    after = None
    while True:
        body = {
            "filterGroups": [{"filters": filters}],
            "properties": ["lifecyclestage"],
            "limit": 100,
        }
        if after:
            body["after"] = after

        for attempt in range(MAX_RETRIES):
            resp = requests.post(
                f"{BASE}/crm/v3/objects/{object_type}/search",
                headers=HEADERS, json=body,
            )
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


def batch_update(object_type, record_ids, property_name, value):
    """Batch update records in groups of BATCH_SIZE with retry."""
    total = len(record_ids)
    updated = 0
    failed = []

    for i in range(0, total, BATCH_SIZE):
        batch = record_ids[i : i + BATCH_SIZE]
        body = {
            "inputs": [
                {"id": rid, "properties": {property_name: value}}
                for rid in batch
            ]
        }

        for attempt in range(MAX_RETRIES):
            resp = requests.post(
                f"{BASE}/crm/v3/objects/{object_type}/batch/update",
                headers=HEADERS, json=body,
            )
            if resp.status_code == 429:
                wait = min(10 * (attempt + 1), 30)
                time.sleep(wait)
                continue
            break

        if resp.status_code in (200, 201):
            updated += len(batch)
            print(f"    Updated {updated:,}/{total:,}")
        else:
            failed.extend(batch)
            print(f"    FAILED batch at {i}: {resp.status_code} — {resp.text[:200]}")
        time.sleep(BATCH_DELAY)

    return updated, failed


def clear_then_set(object_type, record_ids, label):
    """Clear lifecycle stage, then set to Lead.
    This is required because HubSpot lifecycle stages are forward-only.
    """
    if not record_ids:
        return 0, []

    print(f"  Step A: Clearing lifecycle stage for {len(record_ids):,} {label}...")
    cleared, clear_failed = batch_update(
        object_type, record_ids, "lifecyclestage", "",
    )
    if clear_failed:
        print(f"    WARNING: {len(clear_failed)} failed to clear")

    # Only set the ones that were successfully cleared
    ids_to_set = [rid for rid in record_ids if rid not in set(clear_failed)]
    print(f"  Step B: Setting lifecycle stage to Lead for {len(ids_to_set):,} {label}...")
    set_ok, set_failed = batch_update(
        object_type, ids_to_set, "lifecyclestage", "lead",
    )

    total_failed = clear_failed + set_failed
    return set_ok, total_failed


# ── Main ─────────────────────────────────────────────────────────

print("=" * 60)
print("EXECUTE: Fix Lifecycle Stages")
print("=" * 60)
print()

audit_log = []

for obj_type, obj_label in [("contacts", "CONTACTS"), ("companies", "COMPANIES")]:
    print(f"{obj_label}")
    print("-" * 40)

    all_ids = []

    # Collect IDs for each disallowed stage
    for stage in DISALLOWED_STAGES:
        ids = search_all_ids(obj_type, [{
            "propertyName": "lifecyclestage",
            "operator": "EQ",
            "value": stage,
        }])
        print(f"  {stage}: {len(ids):,} {obj_label.lower()} found")
        all_ids.extend(ids)
        audit_log.append({
            "object": obj_type, "stage": stage, "found": len(ids),
        })

    # Empty lifecycle stage
    empty_ids = search_all_ids(obj_type, [{
        "propertyName": "lifecyclestage",
        "operator": "NOT_HAS_PROPERTY",
    }])
    print(f"  (empty): {len(empty_ids):,} {obj_label.lower()} found")
    all_ids.extend(empty_ids)
    audit_log.append({
        "object": obj_type, "stage": "(empty)", "found": len(empty_ids),
    })

    total = len(all_ids)
    print(f"\n  Total {obj_label.lower()} to update: {total:,}")

    if total > SAFETY_THRESHOLD:
        print(f"  SAFETY: Total exceeds threshold ({SAFETY_THRESHOLD:,}). Aborting.")
        continue

    if all_ids:
        updated, failed = clear_then_set(obj_type, all_ids, obj_label.lower())
        print(f"  Done. {updated:,} {obj_label.lower()} set to Lead. "
              f"{len(failed)} failed.")
    else:
        print(f"  No {obj_label.lower()} to update.")
    print()

# ── CSV audit trail ──────────────────────────────────────────────
os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["object", "stage", "found"])
    writer.writeheader()
    writer.writerows(audit_log)
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
print()
print("=" * 60)
print("COMPLETE — All disallowed lifecycle stages moved to Lead")
print("=" * 60)
print()
print("Next steps:")
print("  1. Run after.py to verify zero records in disallowed stages")
print("  2. Create two HubSpot workflows to prevent future occurrences:")
print("     - Contact workflow: if lifecycle = Subscriber/Other/Evangelist/(empty)")
print("       -> set to Lead (with re-enrollment ON)")
print("     - Company workflow: same logic")
