# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Suppress Ghost Contacts — Before State
Count ghost contacts (emails delivered > 0, never opened, never bounced).
Segments by delivery count and exports to CSV.
Uses segmented queries to bypass the 10K pagination limit.
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

# Ghost contact definition:
#   - hs_email_delivered > 0  (received at least one email)
#   - hs_email_open is null   (never opened any — use NOT_HAS_PROPERTY)
#   - hs_email_bounce is null (never bounced — use NOT_HAS_PROPERTY)
GHOST_FILTERS = [
    {"propertyName": "hs_email_delivered", "operator": "GT", "value": "0"},
    {"propertyName": "hs_email_open", "operator": "NOT_HAS_PROPERTY"},
    {"propertyName": "hs_email_bounce", "operator": "NOT_HAS_PROPERTY"},
]

print("=" * 60)
print("SUPPRESS GHOST CONTACTS — BEFORE STATE")
print("=" * 60)
print()

# --- Step 1: Total ghost contacts ---
print("Step 1: Total ghost contacts...")

resp = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": GHOST_FILTERS}],
    "limit": 1,
})
resp.raise_for_status()
total_ghosts = resp.json().get("total", 0)
print(f"  Filters: delivered > 0, opened = null, bounced = null")
print(f"  Total ghost contacts: {total_ghosts}")
print()

# --- Step 2: Marketing status ---
print("Step 2: Ghost contacts still marketing...")

resp2 = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": GHOST_FILTERS + [
        {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
    ]}],
    "limit": 1,
})
resp2.raise_for_status()
still_marketing = resp2.json().get("total", 0)
already_non_marketing = total_ghosts - still_marketing

print(f"  Still marketing: {still_marketing}")
print(f"  Already non-marketing: {already_non_marketing}")
print()

# --- Step 3: Breakdown by delivery volume ---
print("Step 3: Delivery volume breakdown...")

brackets = [
    ("1-10 emails", "0", "10"),
    ("11-25 emails", "10", "25"),
    ("26-50 emails", "25", "50"),
]

for label, gt, lte in brackets:
    resp_b = requests.post(url, headers=headers, json={
        "filterGroups": [{"filters": [
            {"propertyName": "hs_email_delivered", "operator": "GT", "value": gt},
            {"propertyName": "hs_email_delivered", "operator": "LTE", "value": lte},
            {"propertyName": "hs_email_open", "operator": "NOT_HAS_PROPERTY"},
            {"propertyName": "hs_email_bounce", "operator": "NOT_HAS_PROPERTY"},
        ]}],
        "limit": 1,
    })
    if resp_b.status_code == 200:
        count = resp_b.json().get("total", 0)
        print(f"  {label}: {count}")
    time.sleep(PAGINATE_DELAY)

# 50+ emails
resp_50 = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_email_delivered", "operator": "GT", "value": "50"},
        {"propertyName": "hs_email_open", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "hs_email_bounce", "operator": "NOT_HAS_PROPERTY"},
    ]}],
    "limit": 1,
})
if resp_50.status_code == 200:
    print(f"  50+ emails: {resp_50.json().get('total', 0)}")

# Worst offenders — adjust threshold based on your email cadence
WORST_OFFENDER_THRESHOLD = 15  # Configurable: typically 5-15 depending on send frequency
resp_worst = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_email_delivered", "operator": "GT", "value": str(WORST_OFFENDER_THRESHOLD)},
        {"propertyName": "hs_email_open", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "hs_email_bounce", "operator": "NOT_HAS_PROPERTY"},
    ]}],
    "limit": 1,
})
resp_worst.raise_for_status()
worst_offenders = resp_worst.json().get("total", 0)
print(f"\n  {WORST_OFFENDER_THRESHOLD}+ delivered (worst offenders): {worst_offenders}")
print()

# --- Step 4: Save full CSV (segmented by delivery volume to bypass 10K limit) ---
print("Step 4: Saving full audit CSV (segmented to bypass 10K limit)...")

PROPS = ["email", "firstname", "lastname", "hs_email_delivered",
         "hs_email_open", "hs_email_bounce", "hs_marketable_status",
         "lifecyclestage", "createdate"]

# Each segment must be under 10K so we can fully paginate it
SEGMENTS = [
    ("1-5 delivered", "0", "5"),
    ("6-10 delivered", "5", "10"),
    ("11-20 delivered", "10", "20"),
    ("21-35 delivered", "20", "35"),
    ("36-50 delivered", "35", "50"),
    ("51+ delivered", "50", None),
]

all_contacts = []

for label, gt_val, lte_val in SEGMENTS:
    seg_filters = [
        {"propertyName": "hs_email_delivered", "operator": "GT", "value": gt_val},
        {"propertyName": "hs_email_open", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "hs_email_bounce", "operator": "NOT_HAS_PROPERTY"},
    ]
    if lte_val:
        seg_filters.append(
            {"propertyName": "hs_email_delivered", "operator": "LTE", "value": lte_val}
        )

    seg_contacts = []
    after = None
    while True:
        payload = {
            "filterGroups": [{"filters": seg_filters}],
            "properties": PROPS,
            "limit": 100,
        }
        if after:
            payload["after"] = after

        resp = requests.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            print(f"  {label}: stopped at {len(seg_contacts)} (status {resp.status_code})")
            break

        data = resp.json()
        for contact in data.get("results", []):
            props = contact.get("properties", {})
            seg_contacts.append({
                "id": contact["id"],
                "email": props.get("email", ""),
                "firstname": props.get("firstname", ""),
                "lastname": props.get("lastname", ""),
                "emails_delivered": props.get("hs_email_delivered", ""),
                "emails_opened": props.get("hs_email_open", ""),
                "emails_bounced": props.get("hs_email_bounce", ""),
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

    print(f"  {label}: {len(seg_contacts)} contacts")
    all_contacts.extend(seg_contacts)

output_dir = "data/audit-logs"
os.makedirs(output_dir, exist_ok=True)
csv_path = os.path.join(output_dir, "ghost-contacts-before.csv")

with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["id", "email", "firstname", "lastname",
              "emails_delivered", "emails_opened", "emails_bounced",
              "marketable_status", "lifecycle_stage", "createdate"])
    writer.writeheader()
    writer.writerows(all_contacts)

print(f"\n  Total saved: {len(all_contacts)} contacts to {csv_path}")
if len(all_contacts) < total_ghosts:
    print(f"  Warning: missing {total_ghosts - len(all_contacts)} contacts (may need finer segments)")
print()

# --- Step 5: Create HubSpot lists ---
print("Step 5: Creating HubSpot lists...")

# Main ghost list
list1_payload = {
    "name": "CLEANUP: Ghost Contacts - Never Opened",
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
                        "property": "hs_email_delivered",
                        "operation": {
                            "operationType": "NUMBER",
                            "operator": "IS_GREATER_THAN",
                            "value": 0,
                        },
                    },
                    {
                        "filterType": "PROPERTY",
                        "property": "hs_email_open",
                        "operation": {
                            "operationType": "ALL_PROPERTY",
                            "operator": "IS_UNKNOWN",
                        },
                    },
                    {
                        "filterType": "PROPERTY",
                        "property": "hs_email_bounce",
                        "operation": {
                            "operationType": "ALL_PROPERTY",
                            "operator": "IS_UNKNOWN",
                        },
                    },
                ],
            }
        ],
        "filters": [],
    },
}

resp_l1 = requests.post(f"{BASE}/crm/v3/lists", headers=headers, json=list1_payload)
if resp_l1.status_code in (200, 201):
    lid1 = resp_l1.json().get("listId") or resp_l1.json().get("list", {}).get("listId")
    print(f"  Main list created! ID: {lid1}")
elif resp_l1.status_code == 409:
    print(f"  Main list already exists (409 conflict)")
else:
    print(f"  Main list failed ({resp_l1.status_code}): {resp_l1.text[:300]}")

# Worst offender sub-list (above configurable threshold)
list2_payload = {
    "name": "REVIEW: Ghost Contacts - High Delivery No Opens",
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
                        "property": "hs_email_delivered",
                        "operation": {
                            "operationType": "NUMBER",
                            "operator": "IS_GREATER_THAN",
                            "value": WORST_OFFENDER_THRESHOLD,
                        },
                    },
                    {
                        "filterType": "PROPERTY",
                        "property": "hs_email_open",
                        "operation": {
                            "operationType": "ALL_PROPERTY",
                            "operator": "IS_UNKNOWN",
                        },
                    },
                    {
                        "filterType": "PROPERTY",
                        "property": "hs_email_bounce",
                        "operation": {
                            "operationType": "ALL_PROPERTY",
                            "operator": "IS_UNKNOWN",
                        },
                    },
                ],
            }
        ],
        "filters": [],
    },
}

resp_l2 = requests.post(f"{BASE}/crm/v3/lists", headers=headers, json=list2_payload)
if resp_l2.status_code in (200, 201):
    lid2 = resp_l2.json().get("listId") or resp_l2.json().get("list", {}).get("listId")
    print(f"  Review list created! ID: {lid2}")
elif resp_l2.status_code == 409:
    print(f"  Review list already exists (409 conflict)")
else:
    print(f"  Review list failed ({resp_l2.status_code}): {resp_l2.text[:300]}")

# --- Summary ---
print()
print("=" * 60)
print("BEFORE STATE SUMMARY")
print("=" * 60)
print(f"  Total ghost contacts: {total_ghosts}")
print(f"  Already non-marketing: {already_non_marketing}")
print(f"  Still marketing (actionable): {still_marketing}")
print(f"  Worst offenders ({WORST_OFFENDER_THRESHOLD}+ delivered): {worst_offenders}")
print(f"  Contacts in audit CSV: {len(all_contacts)}")
print(f"  Audit CSV: {csv_path}")
print()
print("  Next step: Use HubSpot UI to suppress marketing status")
print("  for contacts in the 'CLEANUP: Ghost Contacts' list.")
print("  (hs_marketable_status is read-only via API)")
