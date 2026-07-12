# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Assign Unowned Contacts — Before State
Count marketing contacts that have no owner assigned.

Outputs:
  1. Total marketing contacts without an owner
  2. Total marketing contacts with an owner
  3. Available owners in the portal (for reference)
  4. CSV audit trail: before_assign_unowned.csv
"""

import csv
import os

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

SEARCH_URL = f"{BASE}/crm/v3/objects/contacts/search"
CSV_FILE = os.path.join("data", "audit-logs", "before_assign_unowned.csv")

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
print("BEFORE STATE: Assign Unowned Marketing Contacts")
print("=" * 60)
print()

# Step 1 — Total contacts
print("Step 1: Total contacts...")
resp_all = requests.get(
    f"{BASE}/crm/v3/objects/contacts", headers=HEADERS, params={"limit": 1},
)
total_contacts = resp_all.json().get("total", 0) if resp_all.status_code == 200 else 0
print(f"  Total contacts in portal: {total_contacts}")
print()

# Step 2 — Marketing contacts without owner
print("Step 2: Marketing contacts without owner...")
unowned_marketing = search_count([
    {"propertyName": "hubspot_owner_id", "operator": "NOT_HAS_PROPERTY"},
    {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
])
print(f"  Unowned marketing contacts: {unowned_marketing}")
print()

# Step 3 — Marketing contacts with owner
print("Step 3: Marketing contacts with owner...")
owned_marketing = search_count([
    {"propertyName": "hubspot_owner_id", "operator": "HAS_PROPERTY"},
    {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
])
print(f"  Owned marketing contacts: {owned_marketing}")
print()

# Step 4 — All contacts without owner (not just marketing)
print("Step 4: All contacts without owner (regardless of marketing status)...")
unowned_all = search_count([
    {"propertyName": "hubspot_owner_id", "operator": "NOT_HAS_PROPERTY"},
])
print(f"  All unowned contacts: {unowned_all}")
print()

# Step 5 — List available owners
print("Step 5: Available owners in portal...")
owners_resp = requests.get(f"{BASE}/crm/v3/owners", headers=HEADERS)
if owners_resp.status_code == 200:
    owners = owners_resp.json().get("results", [])
    print(f"  Total owners: {len(owners)}")
    for owner in owners[:20]:
        email = owner.get("email", "N/A")
        oid = owner.get("id", "N/A")
        name = f"{owner.get('firstName', '')} {owner.get('lastName', '')}".strip()
        print(f"    {oid}: {name} ({email})")
    if len(owners) > 20:
        print(f"    ... and {len(owners) - 20} more")
else:
    print(f"  Could not fetch owners: {owners_resp.status_code}")
print()

# ── CSV audit trail ──────────────────────────────────────────────
rows = [
    {"metric": "total_contacts", "value": total_contacts},
    {"metric": "unowned_marketing_contacts", "value": unowned_marketing},
    {"metric": "owned_marketing_contacts", "value": owned_marketing},
    {"metric": "unowned_all_contacts", "value": unowned_all},
]
os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["metric", "value"])
    writer.writeheader()
    writer.writerows(rows)
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
print()
print("=" * 60)
print("BEFORE STATE SUMMARY")
print("=" * 60)
print(f"  Total contacts:              {total_contacts}")
print(f"  Unowned marketing contacts:  {unowned_marketing}")
print(f"  Owned marketing contacts:    {owned_marketing}")
print(f"  All unowned contacts:        {unowned_all}")
print()
print("  Next step: Run execute.py with TARGET_OWNER_ID set to the")
print("  owner ID you want to assign these contacts to.")
