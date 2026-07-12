# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Build Smart Lists — Execute
Create 10 core HubSpot lists via the Lists API (v3).

Lists created:
  1. All Marketing Contacts
  2. All Leads
  3. All MQLs
  4. All SQLs
  5. All Customers
  6. ICP Tier 1 Companies
  7. ICP Tier 2 Companies
  8. ICP Tier 3 Companies
  9. Engaged (Active Window) — configurable, default 90 days
  10. Unengaged (Re-engagement Window) — configurable, default 180 days

All lists are DYNAMIC (auto-updating smart lists).
Uses HubSpot Lists API v3 (ILS) for creation.

Rate limiting: respects 429 responses with exponential backoff.
Exports CSV audit trail of created list IDs.
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

MAX_RETRIES = 5
BATCH_DELAY = 0.5  # seconds between batch operations (list creations)
CSV_FILE = os.path.join("data", "audit-logs", "execute_build_smart_lists.csv")
TIMEZONE = os.environ.get("HUBSPOT_TIMEZONE", "UTC")

# ── Configurable engagement windows ─────────────────────────────
# Adjust these to match your sales cycle:
#   - ACTIVE_WINDOW_DAYS: 60-120 days typical (shorter for high-velocity, longer for enterprise)
#   - REENGAGEMENT_WINDOW_DAYS: 120-270 days typical
ACTIVE_WINDOW_DAYS = 90
REENGAGEMENT_WINDOW_DAYS = 180

# ICP tier property name — must match whatever you chose in the create-icp-tiers skill
ICP_PROPERTY_NAME = "company_segment"

# ── List definitions ─────────────────────────────────────────────
# HubSpot Lists API v3 uses "filterBranch" for dynamic list definitions.
# Each list has a processingType of "DYNAMIC" for smart lists.

LISTS = [
    {
        "name": "All Marketing Contacts",
        "objectTypeId": "0-1",  # contacts
        "processingType": "DYNAMIC",
        "filterBranch": {
            "filterBranchType": "AND",
            "filterBranches": [],
            "filters": [
                {
                    "filterType": "PROPERTY",
                    "property": "hs_marketable_status",
                    "operation": {
                        "operationType": "STRING",
                        "operator": "IS_EQUAL_TO",
                        "value": "true",
                    },
                },
            ],
        },
    },
    {
        "name": "All Leads",
        "objectTypeId": "0-1",
        "processingType": "DYNAMIC",
        "filterBranch": {
            "filterBranchType": "AND",
            "filterBranches": [],
            "filters": [
                {
                    "filterType": "PROPERTY",
                    "property": "lifecyclestage",
                    "operation": {
                        "operationType": "ENUMERATION",
                        "operator": "IS_EQUAL_TO",
                        "value": "lead",
                    },
                },
            ],
        },
    },
    {
        "name": "All MQLs",
        "objectTypeId": "0-1",
        "processingType": "DYNAMIC",
        "filterBranch": {
            "filterBranchType": "AND",
            "filterBranches": [],
            "filters": [
                {
                    "filterType": "PROPERTY",
                    "property": "lifecyclestage",
                    "operation": {
                        "operationType": "ENUMERATION",
                        "operator": "IS_EQUAL_TO",
                        "value": "marketingqualifiedlead",
                    },
                },
            ],
        },
    },
    {
        "name": "All SQLs",
        "objectTypeId": "0-1",
        "processingType": "DYNAMIC",
        "filterBranch": {
            "filterBranchType": "AND",
            "filterBranches": [],
            "filters": [
                {
                    "filterType": "PROPERTY",
                    "property": "lifecyclestage",
                    "operation": {
                        "operationType": "ENUMERATION",
                        "operator": "IS_EQUAL_TO",
                        "value": "salesqualifiedlead",
                    },
                },
            ],
        },
    },
    {
        "name": "All Customers",
        "objectTypeId": "0-1",
        "processingType": "DYNAMIC",
        "filterBranch": {
            "filterBranchType": "AND",
            "filterBranches": [],
            "filters": [
                {
                    "filterType": "PROPERTY",
                    "property": "lifecyclestage",
                    "operation": {
                        "operationType": "ENUMERATION",
                        "operator": "IS_EQUAL_TO",
                        "value": "customer",
                    },
                },
            ],
        },
    },
    {
        "name": "ICP Tier 1 Companies",
        "objectTypeId": "0-2",  # companies
        "processingType": "DYNAMIC",
        "filterBranch": {
            "filterBranchType": "AND",
            "filterBranches": [],
            "filters": [
                {
                    "filterType": "PROPERTY",
                    "property": ICP_PROPERTY_NAME,
                    "operation": {
                        "operationType": "ENUMERATION",
                        "operator": "IS_EQUAL_TO",
                        "value": "tier_1_primary_icp",
                    },
                },
            ],
        },
    },
    {
        "name": "ICP Tier 2 Companies",
        "objectTypeId": "0-2",
        "processingType": "DYNAMIC",
        "filterBranch": {
            "filterBranchType": "AND",
            "filterBranches": [],
            "filters": [
                {
                    "filterType": "PROPERTY",
                    "property": ICP_PROPERTY_NAME,
                    "operation": {
                        "operationType": "ENUMERATION",
                        "operator": "IS_EQUAL_TO",
                        "value": "tier_2_secondary_icp",
                    },
                },
            ],
        },
    },
    {
        "name": "ICP Tier 3 Companies",
        "objectTypeId": "0-2",
        "processingType": "DYNAMIC",
        "filterBranch": {
            "filterBranchType": "AND",
            "filterBranches": [],
            "filters": [
                {
                    "filterType": "PROPERTY",
                    "property": ICP_PROPERTY_NAME,
                    "operation": {
                        "operationType": "ENUMERATION",
                        "operator": "IS_EQUAL_TO",
                        "value": "tier_3_tertiary_icp",
                    },
                },
            ],
        },
    },
    {
        "name": f"Engaged Last {ACTIVE_WINDOW_DAYS} Days",
        "objectTypeId": "0-1",
        "processingType": "DYNAMIC",
        "filterBranch": {
            "filterBranchType": "OR",
            "filterBranches": [],
            "filters": [
                {
                    "filterType": "PROPERTY",
                    "property": "hs_email_last_open_date",
                    "operation": {
                        "operationType": "TIME_POINT",
                        "operator": "IS_AFTER",
                        "timePoint": {
                            "timeType": "INDEXED",
                            "timezoneSource": "PORTAL",
                            "zoneId": TIMEZONE,
                            "indexReference": {
                                "referenceType": "TODAY",
                            },
                            "offset": {
                                "amount": -ACTIVE_WINDOW_DAYS,
                                "unit": "DAY",
                            },
                        },
                    },
                },
                {
                    "filterType": "PROPERTY",
                    "property": "hs_email_last_click_date",
                    "operation": {
                        "operationType": "TIME_POINT",
                        "operator": "IS_AFTER",
                        "timePoint": {
                            "timeType": "INDEXED",
                            "timezoneSource": "PORTAL",
                            "zoneId": TIMEZONE,
                            "indexReference": {
                                "referenceType": "TODAY",
                            },
                            "offset": {
                                "amount": -ACTIVE_WINDOW_DAYS,
                                "unit": "DAY",
                            },
                        },
                    },
                },
            ],
        },
    },
    {
        "name": f"Unengaged {REENGAGEMENT_WINDOW_DAYS}+ Days",
        "objectTypeId": "0-1",
        "processingType": "DYNAMIC",
        "filterBranch": {
            "filterBranchType": "AND",
            "filterBranches": [],
            "filters": [
                {
                    "filterType": "PROPERTY",
                    "property": "hs_email_last_open_date",
                    "operation": {
                        "operationType": "TIME_POINT",
                        "operator": "IS_BEFORE",
                        "timePoint": {
                            "timeType": "INDEXED",
                            "timezoneSource": "PORTAL",
                            "zoneId": TIMEZONE,
                            "indexReference": {
                                "referenceType": "TODAY",
                            },
                            "offset": {
                                "amount": -REENGAGEMENT_WINDOW_DAYS,
                                "unit": "DAY",
                            },
                        },
                    },
                },
                {
                    "filterType": "PROPERTY",
                    "property": "hs_marketable_status",
                    "operation": {
                        "operationType": "STRING",
                        "operator": "IS_EQUAL_TO",
                        "value": "true",
                    },
                },
            ],
        },
    },
]

# ── Main ─────────────────────────────────────────────────────────

print("=" * 60)
print("EXECUTE: Build Smart Lists")
print("=" * 60)
print()

create_url = f"{BASE}/crm/v3/lists"
audit_log = []
created = 0
skipped = 0
failed = 0

for i, list_def in enumerate(LISTS, 1):
    name = list_def["name"]
    print(f"[{i}/{len(LISTS)}] Creating: {name}...", end=" ")

    for attempt in range(MAX_RETRIES):
        resp = requests.post(create_url, headers=HEADERS, json=list_def)
        if resp.status_code == 429:
            wait = min(10 * (attempt + 1), 30)
            print(f"rate limited, waiting {wait}s...", end=" ")
            time.sleep(wait)
            continue
        break

    if resp.status_code in (200, 201):
        list_id = resp.json().get("listId", resp.json().get("list", {}).get("listId", "unknown"))
        print(f"OK (listId: {list_id})")
        audit_log.append({
            "name": name, "list_id": list_id, "status": "created",
        })
        created += 1
    elif resp.status_code == 409:
        # List with this name already exists
        print("SKIPPED (already exists)")
        audit_log.append({
            "name": name, "list_id": "existing", "status": "skipped",
        })
        skipped += 1
    else:
        print(f"FAILED ({resp.status_code}: {resp.text[:200]})")
        audit_log.append({
            "name": name, "list_id": "", "status": f"failed_{resp.status_code}",
        })
        failed += 1

    time.sleep(BATCH_DELAY)

# ── CSV audit trail ──────────────────────────────────────────────
os.makedirs(os.path.join("data", "audit-logs"), exist_ok=True)
with open(CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["name", "list_id", "status"])
    writer.writeheader()
    writer.writerows(audit_log)
print()
print(f"Audit trail written to {CSV_FILE}")

# ── Summary ──────────────────────────────────────────────────────
print()
print("=" * 60)
print("EXECUTION SUMMARY")
print("=" * 60)
print(f"  Lists created:  {created}")
print(f"  Lists skipped:  {skipped} (already existed)")
print(f"  Lists failed:   {failed}")
print(f"  Total attempted: {len(LISTS)}")
print()
print("  Created lists:")
for entry in audit_log:
    status_icon = "+" if entry["status"] == "created" else \
                  "=" if entry["status"] == "skipped" else "X"
    print(f"    [{status_icon}] {entry['name']} (ID: {entry['list_id']})")
print()
print("  NOTE: Lists are DYNAMIC (smart lists) and will auto-update.")
print(f"  ICP Tier lists require the '{ICP_PROPERTY_NAME}' property to be populated")
print("  by workflows (see create-icp-tiers skill).")
print("=" * 60)
