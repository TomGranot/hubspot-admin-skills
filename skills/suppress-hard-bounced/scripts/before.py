# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Suppress Hard-Bounced Contacts — Before State
Count hard-bounced contacts, export with bounce reasons to CSV.
Optionally creates a HubSpot active list for manual suppression.
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
print("SUPPRESS HARD-BOUNCED CONTACTS — BEFORE STATE")
print("=" * 60)
print()

# --- Step 1: Count hard-bounced contacts ---
print("Step 1: Counting hard-bounced contacts...")

search_payload = {
    "filterGroups": [
        {
            "filters": [
                {
                    "propertyName": "hs_email_hard_bounce_reason_enum",
                    "operator": "HAS_PROPERTY",
                }
            ]
        }
    ],
    "properties": [
        "email", "firstname", "lastname", "hs_email_hard_bounce_reason_enum",
        "hs_email_bounce", "lifecyclestage", "hs_marketable_status", "createdate",
    ],
    "limit": 100,
}

print(f"  API: POST {url}")
print(f"  Filter: hs_email_hard_bounce_reason_enum HAS_PROPERTY")
print()

all_contacts = []
after = None

while True:
    payload = search_payload.copy()
    if after:
        payload["after"] = after

    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()

    for contact in data.get("results", []):
        props = contact.get("properties", {})
        all_contacts.append({
            "id": contact["id"],
            "email": props.get("email", ""),
            "firstname": props.get("firstname", ""),
            "lastname": props.get("lastname", ""),
            "hard_bounce_reason": props.get("hs_email_hard_bounce_reason_enum", ""),
            "bounce_count": props.get("hs_email_bounce", ""),
            "lifecycle_stage": props.get("lifecyclestage", ""),
            "marketable_status": props.get("hs_marketable_status", ""),
            "createdate": props.get("createdate", ""),
        })

    print(f"  Fetched page ({len(data.get('results', []))} contacts, {len(all_contacts)} total)")

    paging = data.get("paging", {})
    next_page = paging.get("next", {})
    after = next_page.get("after")

    if not after:
        break

    time.sleep(PAGINATE_DELAY)

print(f"\n  Total hard-bounced contacts: {len(all_contacts)}")
print()

# --- Step 2: Bounce reason breakdown ---
print("Step 2: Bounce reason breakdown:")
reasons = {}
for c in all_contacts:
    r = c["hard_bounce_reason"] or "(empty)"
    reasons[r] = reasons.get(r, 0) + 1

for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
    print(f"  {reason}: {count}")

# --- Step 3: Marketing status breakdown ---
already_non_marketing = sum(1 for c in all_contacts if c["marketable_status"] == "false")
still_marketing = len(all_contacts) - already_non_marketing
print()
print(f"  Already non-marketing: {already_non_marketing}")
print(f"  Still marketing (need suppression): {still_marketing}")

# High-bounce contacts
# Configurable threshold for "high bounce" classification
HIGH_BOUNCE_THRESHOLD = 3  # minimum bounce count to flag as high-bounce
high_bounce = [c for c in all_contacts if c["bounce_count"] and int(float(c["bounce_count"])) >= HIGH_BOUNCE_THRESHOLD]
print(f"  Contacts with {HIGH_BOUNCE_THRESHOLD}+ bounces: {len(high_bounce)}")
print()

# --- Step 4: Save CSV audit log ---
print("Step 4: Saving audit CSV...")

output_dir = "data/audit-logs"
os.makedirs(output_dir, exist_ok=True)

csv_path = os.path.join(output_dir, "hard-bounced-contacts-before.csv")
fieldnames = ["id", "email", "firstname", "lastname", "hard_bounce_reason",
              "bounce_count", "lifecycle_stage", "marketable_status", "createdate"]

with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_contacts)

print(f"  Saved {len(all_contacts)} contacts to {csv_path}")
print()

# --- Step 5: Create HubSpot active list ---
print("Step 5: Creating HubSpot active list 'CLEANUP: Hard Bounced Contacts'...")

list_payload = {
    "name": "CLEANUP: Hard Bounced Contacts",
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
                        "property": "hs_email_hard_bounce_reason_enum",
                        "operation": {
                            "operationType": "ALL_PROPERTY",
                            "operator": "IS_KNOWN",
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
print(f"  Total hard-bounced contacts: {len(all_contacts)}")
print(f"  Already non-marketing: {already_non_marketing}")
print(f"  Still marketing (actionable): {still_marketing}")
print(f"  High-bounce ({HIGH_BOUNCE_THRESHOLD}+, review for deletion): {len(high_bounce)}")
print(f"  Audit CSV: {csv_path}")
print()
print("  Next step: Use HubSpot UI to suppress marketing status")
print("  for contacts in the 'CLEANUP: Hard Bounced Contacts' list.")
print("  (hs_marketable_status is read-only via API)")
