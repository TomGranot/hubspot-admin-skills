# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Reassign Deactivated Owners — Execute
Batch reassign contacts from deactivated/archived owners to a new owner.

IMPORTANT: Uses archived=True to find deactivated owners.
Handles the 10K search API pagination limit by looping passes.

Usage:
  Set TARGET_OWNER_ID below to the owner ID you want to reassign contacts to.
  Run before.py first to identify valid owner IDs.
"""

import os
import csv
import time
import requests
from dotenv import load_dotenv

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# --- Configuration ---
# Set this to the owner ID that should receive the reassigned contacts.
# Run before.py to see available active owner IDs.
TARGET_OWNER_ID = ""  # e.g., "12345678"

# Safety threshold: abort if total contacts exceeds this number.
# Set to ~120% of your before-state count.
SAFETY_THRESHOLD = 50000

# API pagination and batch limits
BATCH_SIZE = 100          # contacts per batch update
OWNER_PAGE_LIMIT = 500    # max owners per API page
PAGE_SIZE = 100           # contacts per search page
PAGINATE_DELAY = 0.15     # seconds between paginated requests
BATCH_DELAY = 0.5         # seconds between batch operations


def get_archived_owners_with_contacts():
    """Get all archived owners that still have contacts assigned."""
    resp = requests.get(
        f"{BASE}/crm/v3/owners", headers=headers,
        params={"limit": OWNER_PAGE_LIMIT, "archived": "true"},
    )
    resp.raise_for_status()
    archived = resp.json().get("results", [])

    owners = []
    for o in archived:
        oid = o["id"]
        email = o.get("email", "")
        name = f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
        r = requests.post(
            f"{BASE}/crm/v3/objects/contacts/search", headers=headers, json={
                "filterGroups": [{"filters": [
                    {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": str(oid)},
                ]}],
                "limit": 1,
            },
        )
        if r.status_code == 200:
            count = r.json().get("total", 0)
            if count > 0:
                owners.append({"id": oid, "email": email, "name": name, "contacts": count})
        time.sleep(PAGINATE_DELAY)
    return owners


def get_contact_ids_for_owner(owner_id, limit=PAGE_SIZE):
    """Get contact IDs for a given owner using pagination.
    HubSpot search API caps at 10,000 results. The caller should
    loop until no more contacts remain for this owner."""
    contact_ids = []
    after = None
    while True:
        payload = {
            "filterGroups": [{"filters": [
                {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": str(owner_id)},
            ]}],
            "properties": ["email"],
            "limit": limit,
        }
        if after:
            payload["after"] = after

        r = requests.post(
            f"{BASE}/crm/v3/objects/contacts/search", headers=headers, json=payload,
        )
        if r.status_code == 400:
            # Hit the 10K search limit — return what we have
            break
        r.raise_for_status()
        data = r.json()
        results = data.get("results", [])
        if not results:
            break
        for c in results:
            contact_ids.append(c["id"])
        paging = data.get("paging", {})
        if paging.get("next"):
            after = paging["next"]["after"]
            time.sleep(PAGINATE_DELAY)
        else:
            break
    return contact_ids


def batch_update_owner(contact_ids, new_owner_id):
    """Update contact owner in batches of 100."""
    success = 0
    failed = 0
    for i in range(0, len(contact_ids), BATCH_SIZE):
        batch = contact_ids[i:i + BATCH_SIZE]
        payload = {
            "inputs": [
                {"id": cid, "properties": {"hubspot_owner_id": new_owner_id}}
                for cid in batch
            ]
        }
        r = requests.post(
            f"{BASE}/crm/v3/objects/contacts/batch/update", headers=headers, json=payload,
        )
        if r.status_code == 200:
            success += len(batch)
        else:
            failed += len(batch)
            print(f"    Batch failed: {r.status_code} — {r.text[:200]}")
        time.sleep(BATCH_DELAY)
    return success, failed


def main():
    print("=" * 70)
    print("REASSIGN DEACTIVATED OWNERS — EXECUTE")
    print("=" * 70)
    print()

    if not TARGET_OWNER_ID:
        print("ERROR: TARGET_OWNER_ID is not set.")
        print("  Edit this script and set TARGET_OWNER_ID to the owner ID")
        print("  that should receive the reassigned contacts.")
        print("  Run before.py to see available active owner IDs.")
        exit(1)

    # Verify target owner exists and is active
    resp = requests.get(f"{BASE}/crm/v3/owners/{TARGET_OWNER_ID}", headers=headers)
    if resp.status_code != 200:
        print(f"ERROR: Could not find owner with ID {TARGET_OWNER_ID}")
        print(f"  Status: {resp.status_code}")
        exit(1)

    target_info = resp.json()
    target_name = f"{target_info.get('firstName', '')} {target_info.get('lastName', '')}".strip()
    target_email = target_info.get("email", "")
    print(f"Target owner: {target_name} ({target_email}) — ID: {TARGET_OWNER_ID}")
    print()

    # Find deactivated owners with contacts
    print("Finding deactivated owners with assigned contacts...")
    owners = get_archived_owners_with_contacts()
    total_contacts = sum(o["contacts"] for o in owners)

    print(f"\nFound {len(owners)} deactivated owners with {total_contacts} total contacts")
    for o in owners:
        print(f"  {o['name']} ({o['email']}): {o['contacts']} contacts")
    print()

    # Safety check
    if total_contacts > SAFETY_THRESHOLD:
        print(f"SAFETY ABORT: {total_contacts} contacts exceeds threshold of {SAFETY_THRESHOLD}.")
        print("  Update SAFETY_THRESHOLD in this script if this count is expected.")
        exit(1)

    if total_contacts == 0:
        print("No contacts to reassign. Exiting.")
        exit(0)

    # User confirmation
    print(f"About to reassign {total_contacts} contacts to {target_name} ({target_email}).")
    confirm = input("Type 'REASSIGN' to confirm: ")
    if confirm != "REASSIGN":
        print("Aborted by user.")
        exit(0)
    print()

    # Execute reassignment
    total_success = 0
    total_failed = 0
    results_log = []

    for o in sorted(owners, key=lambda x: -x["contacts"]):
        print(f"  Processing: {o['name']} ({o['contacts']} contacts)...")
        owner_success = 0
        owner_failed = 0
        pass_num = 0

        while True:
            pass_num += 1
            contact_ids = get_contact_ids_for_owner(o["id"])
            if not contact_ids:
                break
            print(f"    Pass {pass_num}: fetched {len(contact_ids)} contact IDs")
            s, f = batch_update_owner(contact_ids, TARGET_OWNER_ID)
            owner_success += s
            owner_failed += f
            print(f"    Updated: {s}, Failed: {f}")
            if f > 0:
                break  # stop if hitting errors
            time.sleep(BATCH_DELAY)

        total_success += owner_success
        total_failed += owner_failed
        results_log.append({
            "owner_name": o["name"],
            "owner_id": o["id"],
            "original_count": o["contacts"],
            "reassigned": owner_success,
            "failed": owner_failed,
        })
        print(f"    Total for {o['name']}: {owner_success} reassigned, {owner_failed} failed")

    # Save execution log
    output_dir = "data/audit-logs"
    os.makedirs(output_dir, exist_ok=True)

    log_path = os.path.join(output_dir, "deactivated-owners-reassignment-log.csv")
    with open(log_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "owner_name", "owner_id", "original_count", "reassigned", "failed",
        ])
        writer.writeheader()
        writer.writerows(results_log)

    # Summary
    print()
    print("=" * 70)
    print("EXECUTION SUMMARY")
    print("=" * 70)
    print(f"  Target owner: {target_name} ({target_email})")
    print(f"  Total reassigned: {total_success}")
    print(f"  Total failed:     {total_failed}")
    print(f"  Execution log: {log_path}")
    print()
    print("  Next step: Run after.py to verify reassignment.")


if __name__ == "__main__":
    main()
