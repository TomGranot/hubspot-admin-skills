# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Reassign Deactivated Owners — After State
Verify that no contacts remain assigned to deactivated owners.
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

PAGINATE_DELAY = 0.15  # seconds between paginated requests

print("=" * 60)
print("REASSIGN DEACTIVATED OWNERS — AFTER STATE")
print("=" * 60)
print()

# --- Step 1: Get deactivated owners ---
print("Step 1: Checking deactivated owners for remaining contacts...")

resp = requests.get(
    f"{BASE}/crm/v3/owners", headers=headers,
    params={"limit": 500, "archived": "true"},
)
resp.raise_for_status()
archived = resp.json().get("results", [])

url = f"{BASE}/crm/v3/objects/contacts/search"
remaining_total = 0
owners_with_contacts = []

for o in archived:
    oid = o["id"]
    name = f"{o.get('firstName', '')} {o.get('lastName', '')}".strip()
    email = o.get("email", "")

    r = requests.post(url, headers=headers, json={
        "filterGroups": [{"filters": [
            {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": str(oid)},
        ]}],
        "limit": 1,
    })
    if r.status_code == 200:
        count = r.json().get("total", 0)
        if count > 0:
            remaining_total += count
            owners_with_contacts.append({"name": name, "email": email, "id": oid, "count": count})
            print(f"  {name} ({email}): {count} contacts remaining")
    time.sleep(PAGINATE_DELAY)

if not owners_with_contacts:
    print("  No deactivated owners have remaining contacts.")

# --- Step 2: Check unassigned contacts ---
print()
print("Step 2: Counting unassigned contacts (no owner)...")

resp_no_owner = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hubspot_owner_id", "operator": "NOT_HAS_PROPERTY"},
    ]}],
    "limit": 1,
})
resp_no_owner.raise_for_status()
unassigned = resp_no_owner.json().get("total", 0)
print(f"  Unassigned contacts: {unassigned}")

# --- Compare with before state ---
before_csv = os.path.join(
    os.path.dirname(__file__), "..", "data", "deactivated-owners-before.csv"
)
if os.path.exists(before_csv):
    with open(before_csv, "r") as f:
        reader = csv.DictReader(f)
        before_data = [r for r in reader if r.get("status") == "deactivated"]
    before_total = sum(int(r.get("contacts", 0) or 0) for r in before_data)
    print()
    print(f"  Before-state contacts with deactivated owners: {before_total}")
    print(f"  Remaining: {remaining_total}")
    print(f"  Reassigned: {before_total - remaining_total}")

# --- Verdict ---
print()
print("=" * 60)
if remaining_total == 0:
    print("SUCCESS: No contacts remain assigned to deactivated owners.")
else:
    print(f"WARNING: {remaining_total} contacts still assigned to deactivated owners:")
    for o in owners_with_contacts:
        print(f"  {o['name']} ({o['email']}): {o['count']}")
    print("  Action: Re-run execute.py or investigate failures.")
print("=" * 60)
