# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Delete No-Email Contacts — Execute
Delete all contacts with no email address in batches with safety threshold.
"""

import os
import csv
import time
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# --- Configuration ---
# Safety threshold: abort if more contacts found than expected.
# Set based on your before-state count, recommend 120% of expected.
SAFETY_THRESHOLD = 1000
BATCH_SIZE = 100
PAGINATE_DELAY = 0.15  # seconds between paginated requests
BATCH_DELAY = 0.5      # seconds between batch operations

print("=" * 60)
print("DELETE NO-EMAIL CONTACTS — EXECUTE")
print("=" * 60)
print()

# --- Step 1: Collect all contact IDs with no email ---
print("Step 1: Collecting all contact IDs with no email...")

all_ids = []
after = None

while True:
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "email",
                        "operator": "NOT_HAS_PROPERTY",
                    }
                ]
            }
        ],
        "properties": ["hs_object_id"],
        "limit": 100,
    }
    if after:
        payload["after"] = after

    url = f"{BASE}/crm/v3/objects/contacts/search"
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()

    batch_ids = [r["id"] for r in data.get("results", [])]
    all_ids.extend(batch_ids)
    print(f"  Fetched {len(batch_ids)} IDs (total so far: {len(all_ids)})")

    paging = data.get("paging", {})
    next_page = paging.get("next", {})
    after = next_page.get("after")

    if not after:
        break

    time.sleep(PAGINATE_DELAY)

print(f"\n  Total contacts to delete: {len(all_ids)}")
print()

# --- Safety check ---
if len(all_ids) > SAFETY_THRESHOLD:
    print(f"SAFETY ABORT: Found {len(all_ids)} contacts, exceeds threshold of {SAFETY_THRESHOLD}.")
    print("  Update SAFETY_THRESHOLD in this script if this count is expected.")
    print("  Exiting without deleting anything.")
    exit(1)

if len(all_ids) == 0:
    print("No contacts to delete. Exiting.")
    exit(0)

# --- User confirmation ---
print(f"About to permanently delete {len(all_ids)} contacts.")
confirm = input("Type 'DELETE' to confirm: ")
if confirm != "DELETE":
    print("Aborted by user.")
    exit(0)
print()

# --- Step 2: Batch delete ---
print("Step 2: Batch deleting contacts...")

deleted_count = 0
failed_ids = []

for i in range(0, len(all_ids), BATCH_SIZE):
    batch = all_ids[i : i + BATCH_SIZE]
    batch_num = (i // BATCH_SIZE) + 1
    total_batches = (len(all_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    delete_url = f"{BASE}/crm/v3/objects/contacts/batch/archive"
    delete_payload = {"inputs": [{"id": cid} for cid in batch]}

    print(f"  Batch {batch_num}/{total_batches}: deleting {len(batch)} contacts...", end=" ")

    resp = requests.post(delete_url, headers=headers, json=delete_payload)

    if resp.status_code == 204:
        deleted_count += len(batch)
        print("OK")
    else:
        failed_ids.extend(batch)
        print(f"FAILED (status {resp.status_code}: {resp.text[:200]})")

    time.sleep(BATCH_DELAY)

# --- Step 3: Save deletion log ---
output_dir = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(output_dir, exist_ok=True)

log_path = os.path.join(output_dir, "no-email-contacts-deleted.csv")
with open(log_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["contact_id", "status"])
    for cid in all_ids:
        status = "failed" if cid in failed_ids else "deleted"
        writer.writerow([cid, status])

print(f"\n  Deletion log saved to {log_path}")

# --- Summary ---
print()
print("=" * 60)
print("EXECUTION SUMMARY")
print("=" * 60)
print(f"  Total contacts found:   {len(all_ids)}")
print(f"  Successfully deleted:   {deleted_count}")
print(f"  Failed:                 {len(failed_ids)}")
if failed_ids:
    print(f"  Failed IDs (first 20):  {failed_ids[:20]}")
print(f"  Deletion log: {log_path}")
print()
print("  Next step: Run after.py to verify deletion.")
