# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Suppress Global Unsubscribes — Before State
Count globally unsubscribed contacts, lifecycle breakdown, export to CSV.
Note: >10K results requires segmented queries or count-only approach.
"""

import os
import csv
import json
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

url = f"{BASE}/crm/v3/objects/contacts/search"

PAGINATE_DELAY = 0.15  # seconds between paginated requests

print("=" * 60)
print("SUPPRESS GLOBAL UNSUBSCRIBES — BEFORE STATE")
print("=" * 60)
print()

# --- Step 1: Total count of globally unsubscribed ---
print("Step 1: Total globally unsubscribed contacts...")

resp = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_email_optout", "operator": "EQ", "value": "true"}
    ]}],
    "limit": 1,
})
resp.raise_for_status()
total_unsubscribed = resp.json().get("total", 0)
print(f"  Filter: hs_email_optout EQ true")
print(f"  Total: {total_unsubscribed}")
print()

# --- Step 2: How many are still marketing? ---
print("Step 2: Unsubscribed AND still marketing...")

resp2 = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_email_optout", "operator": "EQ", "value": "true"},
        {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
    ]}],
    "limit": 1,
})
resp2.raise_for_status()
still_marketing = resp2.json().get("total", 0)
already_non_marketing = total_unsubscribed - still_marketing

print(f"  Still marketing: {still_marketing}")
print(f"  Already non-marketing: {already_non_marketing}")
print()

# --- Step 3: Lifecycle stage breakdown ---
print("Step 3: Lifecycle stage breakdown...")

STAGES = [
    "lead", "subscriber", "marketingqualifiedlead", "salesqualifiedlead",
    "opportunity", "customer", "evangelist", "other",
]

for stage in STAGES:
    resp_s = requests.post(url, headers=headers, json={
        "filterGroups": [{"filters": [
            {"propertyName": "hs_email_optout", "operator": "EQ", "value": "true"},
            {"propertyName": "lifecyclestage", "operator": "EQ", "value": stage},
        ]}],
        "limit": 1,
    })
    if resp_s.status_code == 200:
        count = resp_s.json().get("total", 0)
        if count > 0:
            print(f"  {stage}: {count}")
    time.sleep(PAGINATE_DELAY)

# Check empty lifecycle stage
resp_empty = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_email_optout", "operator": "EQ", "value": "true"},
        {"propertyName": "lifecyclestage", "operator": "NOT_HAS_PROPERTY"},
    ]}],
    "limit": 1,
})
if resp_empty.status_code == 200:
    empty_count = resp_empty.json().get("total", 0)
    if empty_count > 0:
        print(f"  (no lifecycle stage): {empty_count}")
print()

# --- Step 4: Save CSV (first 10K — API pagination limit) ---
print("Step 4: Saving audit CSV (first 10K — API pagination limit)...")

all_contacts = []
after = None

while len(all_contacts) < 10000:
    payload = {
        "filterGroups": [{"filters": [
            {"propertyName": "hs_email_optout", "operator": "EQ", "value": "true"}
        ]}],
        "properties": ["email", "firstname", "lastname", "hs_email_optout",
                       "hs_marketable_status", "lifecyclestage", "createdate"],
        "limit": 100,
    }
    if after:
        payload["after"] = after

    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"  Stopped at {len(all_contacts)} (status {resp.status_code})")
        break

    data = resp.json()
    for contact in data.get("results", []):
        props = contact.get("properties", {})
        all_contacts.append({
            "id": contact["id"],
            "email": props.get("email", ""),
            "firstname": props.get("firstname", ""),
            "lastname": props.get("lastname", ""),
            "unsubscribed": props.get("hs_email_optout", ""),
            "marketable_status": props.get("hs_marketable_status", ""),
            "lifecycle_stage": props.get("lifecyclestage", ""),
            "createdate": props.get("createdate", ""),
        })

    paging = data.get("paging", {})
    next_page = paging.get("next", {})
    after = next_page.get("after")

    if not after:
        break
    time.sleep(PAGINATE_DELAY)

output_dir = "data/audit-logs"
os.makedirs(output_dir, exist_ok=True)
csv_path = os.path.join(output_dir, "global-unsubscribes-before.csv")

with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["id", "email", "firstname", "lastname",
              "unsubscribed", "marketable_status", "lifecycle_stage", "createdate"])
    writer.writeheader()
    writer.writerows(all_contacts)

print(f"  Saved {len(all_contacts)} contacts to {csv_path}")
if total_unsubscribed > 10000:
    print(f"  Note: {total_unsubscribed - len(all_contacts)} contacts beyond 10K API limit not in CSV")
print()

# --- Step 5: Create HubSpot active list ---
print("Step 5: Creating HubSpot active list 'CLEANUP: Globally Unsubscribed'...")

list_payload = {
    "name": "CLEANUP: Globally Unsubscribed",
    "objectTypeId": "0-1",
    "processingType": "DYNAMIC",
    "filterBranch": {
        "filterBranchType": "OR",
        "filterBranches": [
            {
                "filterBranchType": "AND",
                "filterBranches": [],
                "filters": [
                    {
                        "filterType": "PROPERTY",
                        "property": "hs_email_optout",
                        "operation": {
                            "operationType": "ENUMERATION",
                            "operator": "IS_EQUAL_TO",
                            "value": "true",
                        },
                    }
                ],
            }
        ],
        "filters": [],
    },
}

resp = requests.post(f"{BASE}/crm/v3/lists", headers=headers, json=list_payload)

if resp.status_code in (200, 201):
    list_data = resp.json()
    list_id = list_data.get("listId") or list_data.get("list", {}).get("listId")
    print(f"  List created! ID: {list_id}")
elif resp.status_code == 409:
    print(f"  List already exists (409 conflict)")
else:
    print(f"  Failed to create list (status {resp.status_code})")
    print(f"  Response: {resp.text[:300]}")

# --- Summary ---
print()
print("=" * 60)
print("BEFORE STATE SUMMARY")
print("=" * 60)
print(f"  Total globally unsubscribed: {total_unsubscribed}")
print(f"  Already non-marketing: {already_non_marketing}")
print(f"  Still marketing (actionable): {still_marketing}")
print(f"  Contacts in audit CSV: {len(all_contacts)}")
print(f"  Audit CSV: {csv_path}")
print()
print("  Next step: Use HubSpot UI to suppress marketing status")
print("  for contacts in the 'CLEANUP: Globally Unsubscribed' list.")
print("  (hs_marketable_status is read-only via API)")
