# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Reassign Deactivated Owners — Before State
Find deactivated/archived owners and count their contacts and companies.
IMPORTANT: Uses archived=True parameter to find deactivated owners —
the default owners endpoint only returns active owners.
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

PAGINATE_DELAY = 0.15  # seconds between paginated requests

print("=" * 60)
print("REASSIGN DEACTIVATED OWNERS — BEFORE STATE")
print("=" * 60)
print()

# --- Step 1: Get all owners (active + deactivated) ---
print("Step 1: Fetching HubSpot owners...")

# Active owners
resp_active = requests.get(f"{BASE}/crm/v3/owners", headers=headers, params={"limit": 500})
resp_active.raise_for_status()
active_raw = resp_active.json().get("results", [])

# Deactivated owners — MUST pass archived=true
resp_archived = requests.get(f"{BASE}/crm/v3/owners", headers=headers, params={"limit": 500, "archived": "true"})
resp_archived.raise_for_status()
archived_raw = resp_archived.json().get("results", [])

active_owners = []
for o in active_raw:
    if not o.get("archived", False):
        active_owners.append({
            "id": o.get("id"),
            "userId": o.get("userId"),
            "email": o.get("email", ""),
            "firstName": o.get("firstName", ""),
            "lastName": o.get("lastName", ""),
        })

deactivated_owners = []
for o in archived_raw:
    deactivated_owners.append({
        "id": o.get("id"),
        "userId": o.get("userId"),
        "email": o.get("email", ""),
        "firstName": o.get("firstName", ""),
        "lastName": o.get("lastName", ""),
    })

print(f"  Active owners: {len(active_owners)}")
print(f"  Deactivated/archived owners: {len(deactivated_owners)}")
print()

print("  Active owners:")
for o in active_owners:
    print(f"    {o['firstName']} {o['lastName']} ({o['email']}) — ID: {o['id']}")

print()
print("  Deactivated owners:")
for o in deactivated_owners:
    print(f"    {o['firstName']} {o['lastName']} ({o['email']}) — ID: {o['id']}")
print()

# --- Step 2: Count contacts per deactivated owner ---
print("Step 2: Counting contacts per deactivated owner...")

url = f"{BASE}/crm/v3/objects/contacts/search"
deactivated_contact_counts = {}
total_deactivated_contacts = 0

for o in deactivated_owners:
    owner_id = o["id"]
    name = f"{o['firstName']} {o['lastName']}"
    resp = requests.post(url, headers=headers, json={
        "filterGroups": [{"filters": [
            {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": str(owner_id)},
        ]}],
        "limit": 1,
    })
    if resp.status_code == 200:
        count = resp.json().get("total", 0)
        deactivated_contact_counts[name] = {"id": owner_id, "count": count}
        total_deactivated_contacts += count
        if count > 0:
            print(f"  {name}: {count} contacts")
    time.sleep(PAGINATE_DELAY)

print(f"\n  Total contacts owned by deactivated users: {total_deactivated_contacts}")
print()

# --- Step 3: Count unassigned contacts ---
print("Step 3: Counting unassigned contacts (no owner)...")

resp_no_owner = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hubspot_owner_id", "operator": "NOT_HAS_PROPERTY"},
    ]}],
    "limit": 1,
})
resp_no_owner.raise_for_status()
unassigned_contacts = resp_no_owner.json().get("total", 0)
print(f"  Unassigned contacts: {unassigned_contacts}")
print()

# --- Step 4: Count companies per deactivated owner ---
print("Step 4: Counting companies per deactivated owner...")

comp_url = f"{BASE}/crm/v3/objects/companies/search"
deactivated_company_counts = {}
total_deactivated_companies = 0

for o in deactivated_owners:
    owner_id = o["id"]
    name = f"{o['firstName']} {o['lastName']}"
    resp = requests.post(comp_url, headers=headers, json={
        "filterGroups": [{"filters": [
            {"propertyName": "hubspot_owner_id", "operator": "EQ", "value": str(owner_id)},
        ]}],
        "limit": 1,
    })
    if resp.status_code == 200:
        count = resp.json().get("total", 0)
        deactivated_company_counts[name] = {"id": owner_id, "count": count}
        total_deactivated_companies += count
        if count > 0:
            print(f"  {name}: {count} companies")
    time.sleep(PAGINATE_DELAY)

print(f"\n  Total companies owned by deactivated users: {total_deactivated_companies}")
print()

# --- Step 5: Save CSV audit log ---
print("Step 5: Saving audit CSV...")

output_dir = "data/audit-logs"
os.makedirs(output_dir, exist_ok=True)

summary_path = os.path.join(output_dir, "deactivated-owners-before.csv")
with open(summary_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["owner_name", "owner_id", "email", "status", "contacts", "companies"])
    writer.writeheader()
    for o in deactivated_owners:
        name = f"{o['firstName']} {o['lastName']}"
        writer.writerow({
            "owner_name": name,
            "owner_id": o["id"],
            "email": o["email"],
            "status": "deactivated",
            "contacts": deactivated_contact_counts.get(name, {}).get("count", 0),
            "companies": deactivated_company_counts.get(name, {}).get("count", 0),
        })
    for o in active_owners:
        name = f"{o['firstName']} {o['lastName']}"
        writer.writerow({
            "owner_name": name,
            "owner_id": o["id"],
            "email": o["email"],
            "status": "active",
            "contacts": "",
            "companies": "",
        })

print(f"  Saved ownership summary to {summary_path}")
print()

# --- Summary ---
print("=" * 60)
print("BEFORE STATE SUMMARY")
print("=" * 60)
print(f"  Deactivated owners: {len(deactivated_owners)}")
print(f"  Contacts owned by deactivated users: {total_deactivated_contacts}")
print(f"  Unassigned contacts (no owner): {unassigned_contacts}")
print(f"  Companies owned by deactivated users: {total_deactivated_companies}")
print(f"  Audit CSV: {summary_path}")
print()
print("  Next step: Choose a target owner, then run execute.py to reassign.")
