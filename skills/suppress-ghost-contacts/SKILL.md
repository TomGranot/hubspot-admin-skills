---
name: suppress-ghost-contacts
description: "Identify and suppress ghost contacts who received marketing emails but never opened any. These contacts destroy sender reputation and deliverability. Hybrid approach: API for discovery, manual UI for suppression."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: database-hygiene
---

# Suppress Ghost Contacts (Delivered, Never Opened)

## Purpose

Ghost contacts have received marketing emails but have never opened a single one. They are the largest threat to email deliverability because ISPs like Gmail and Microsoft track engagement at the sender level. Consistently sending to people who never open signals that the sender is producing unwanted email, causing inbox placement to deteriorate even for engaged contacts.

## Prerequisites

- A HubSpot private app access token with `crm.objects.contacts.read` and `crm.lists.read`/`crm.lists.write` scopes
- Python 3.10+ with `uv` for package management
- A `.env` file containing `HUBSPOT_ACCESS_TOKEN`
- Super Admin or Marketing Hub Admin permissions for the manual UI suppression step

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/suppress-ghost-contacts/scripts/before.py` |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run skills/suppress-ghost-contacts/scripts/after.py` |

There is no execute script: the marketing-status change itself must happen via a HubSpot workflow or the UI (see Key Constraint and Stage 3).

## Key Constraint

**`hs_marketable_status` is read-only via the API.** Suppression must happen in the HubSpot UI.

## CRITICAL: "Never Opened" Is Null, Not Zero

HubSpot stores "never opened" as a **null/absent property**, not as the number 0. You **MUST** use the `NOT_HAS_PROPERTY` operator to find contacts who have never opened an email. Using `EQ 0` will return zero results because the property is not set at all for these contacts.

```python
# CORRECT - finds contacts who have never opened
{"propertyName": "hs_email_open", "operator": "NOT_HAS_PROPERTY"}

# WRONG - returns nothing because the property does not exist on these contacts
{"propertyName": "hs_email_open", "operator": "EQ", "value": "0"}
```

The same applies to `hs_email_bounce` -- "never bounced" is also null.

## Execution Pattern

This skill follows a 4-stage execution pattern: **Plan -> Before -> Execute -> After**.

### Stage 1: Plan

Before writing any code, confirm with the user:

1. **Graduated approach**: Recommend suppressing only contacts above your delivery threshold (typically 5-15, adjust based on your email cadence) first. Contacts below that threshold may not have had enough chances to engage.
2. **Overlap with previous processes**: Some ghost contacts may already be non-marketing from hard-bounce or unsubscribe suppression. The Before State will measure this overlap.
3. **Open tracking caveat**: Some email clients block tracking pixels. However, at the scale of thousands of contacts with zero opens across multiple sends, the overwhelming majority are genuinely unengaged.
4. **Apple Mail Privacy Protection**: Introduced in iOS 15 / macOS Monterey, it pre-loads tracking pixels, which can create false-positive opens. Contacts who do NOT show opens despite this feature are almost certainly truly unengaged.

### Stage 2: Before

Discover all ghost contacts, break down by delivery volume, and generate an audit CSV.

```python
"""
Before State: Count and audit ghost contacts.
Definition: emails delivered > 0, emails opened = null, emails bounced = null.
"""
import os
import csv
import time
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

url = f"{BASE}/crm/v3/objects/contacts/search"

# Ghost contact filter definition
GHOST_FILTERS = [
    {"propertyName": "hs_email_delivered", "operator": "GT", "value": "0"},
    {"propertyName": "hs_email_open", "operator": "NOT_HAS_PROPERTY"},
    {"propertyName": "hs_email_bounce", "operator": "NOT_HAS_PROPERTY"},
]

# --- Step 1: Total ghost contacts ---
resp = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": GHOST_FILTERS}],
    "limit": 1,
})
resp.raise_for_status()
total_ghosts = resp.json().get("total", 0)
print(f"Total ghost contacts: {total_ghosts}")

# --- Step 2: How many are still marketing? ---
resp2 = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": GHOST_FILTERS + [
        {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
    ]}],
    "limit": 1,
})
resp2.raise_for_status()
still_marketing = resp2.json().get("total", 0)
already_non_marketing = total_ghosts - still_marketing
print(f"Still marketing: {still_marketing}")
print(f"Already non-marketing (from prior processes): {already_non_marketing}")

# --- Step 3: Breakdown by delivery volume ---
print("\nGhost contacts by delivery volume:")
brackets = [
    ("1-10 emails", "0", "10"),
    ("11-25 emails", "10", "25"),
    ("26-50 emails", "25", "50"),
]

for label, gt_val, lte_val in brackets:
    resp_b = requests.post(url, headers=headers, json={
        "filterGroups": [{"filters": [
            {"propertyName": "hs_email_delivered", "operator": "GT", "value": gt_val},
            {"propertyName": "hs_email_delivered", "operator": "LTE", "value": lte_val},
            {"propertyName": "hs_email_open", "operator": "NOT_HAS_PROPERTY"},
            {"propertyName": "hs_email_bounce", "operator": "NOT_HAS_PROPERTY"},
        ]}],
        "limit": 1,
    })
    if resp_b.status_code == 200:
        print(f"  {label}: {resp_b.json().get('total', 0)}")
    time.sleep(0.1)

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

# Worst offenders count (above your delivery threshold)
WORST_OFFENDER_THRESHOLD = 15  # Adjust based on your email cadence (typically 5-15)
resp_worst = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_email_delivered", "operator": "GT", "value": str(WORST_OFFENDER_THRESHOLD - 1)},
        {"propertyName": "hs_email_open", "operator": "NOT_HAS_PROPERTY"},
        {"propertyName": "hs_email_bounce", "operator": "NOT_HAS_PROPERTY"},
    ]}],
    "limit": 1,
})
resp_worst.raise_for_status()
worst_offenders = resp_worst.json().get("total", 0)
print(f"\n{WORST_OFFENDER_THRESHOLD}+ delivered (recommended for immediate suppression): {worst_offenders}")
```

**Step 4: Export full CSV using segmented queries**

The Search API caps at 10K results. For ghost contacts (often >10K), segment by delivery volume brackets to bypass the limit.

```python
# --- Step 4: Full CSV export using segmented queries ---
PROPS = [
    "email", "firstname", "lastname", "hs_email_delivered",
    "hs_email_open", "hs_email_bounce", "hs_marketable_status",
    "lifecyclestage", "createdate",
]

# Each segment must be under 10K for full pagination
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

    after = None
    seg_count = 0
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
            break

        data = resp.json()
        for contact in data.get("results", []):
            props = contact.get("properties", {})
            all_contacts.append({
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
            seg_count += 1

        paging = data.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after:
            break
        time.sleep(0.12)

    print(f"  {label}: {seg_count} contacts")

os.makedirs("data/audit-logs", exist_ok=True)
csv_path = "data/audit-logs/ghost-contacts.csv"

with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "id", "email", "firstname", "lastname", "emails_delivered",
        "emails_opened", "emails_bounced", "marketable_status",
        "lifecycle_stage", "createdate",
    ])
    writer.writeheader()
    writer.writerows(all_contacts)

print(f"\nAudit CSV saved: {csv_path} ({len(all_contacts)} records)")
```

### Stage 3: Execute

**Step 3a: Create HubSpot active lists via API**

Create two lists: a main suppression list and a worst-offender review list.

```python
"""
Execute (API part): Create HubSpot active lists.
"""

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

resp1 = requests.post(f"{BASE}/crm/v3/lists", headers=headers, json=list1_payload)
if resp1.status_code in (200, 201):
    lid1 = resp1.json().get("listId") or resp1.json().get("list", {}).get("listId")
    print(f"Main list created! ID: {lid1}")
elif resp1.status_code == 409:
    print("Main list already exists.")

# Worst-offender sub-list (above your delivery threshold)
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
                            "value": 14,  # Adjust to match your delivery threshold minus 1
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

resp2 = requests.post(f"{BASE}/crm/v3/lists", headers=headers, json=list2_payload)
if resp2.status_code in (200, 201):
    lid2 = resp2.json().get("listId") or resp2.json().get("list", {}).get("listId")
    print(f"Review list created! ID: {lid2}")
elif resp2.status_code == 409:
    print("Review list already exists.")
```

**Step 3b: Suppress contacts in HubSpot UI**

Instruct the user:

1. Open the list **"CLEANUP: Ghost Contacts - Never Opened"** in HubSpot
2. Click the checkbox in the table header row
3. Click **"Select all N contacts in this list"**
4. Click **More** > **Set marketing contact status**
5. Select **Set as non-marketing contact**
6. Click **Confirm**

**Graduated approach recommendation**: If the user prefers a conservative approach, suppress only the **"REVIEW: Ghost Contacts - High Delivery No Opens"** list first. Monitor contacts below your delivery threshold separately -- they may engage with future emails.

**Step 3c: Keep both lists active permanently**

- The main list captures new ghost contacts over time as emails are sent
- The review list grows as contacts accumulate more delivered emails with no engagement
- Run suppression monthly; review for deletion quarterly

### Stage 4: After

Re-run the Before State queries and compare.

```python
"""
After State: Verify ghost contacts have been suppressed.
"""
# Re-check still-marketing count
resp = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": GHOST_FILTERS + [
        {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
    ]}],
    "limit": 1,
})
resp.raise_for_status()
remaining = resp.json().get("total", 0)

if remaining == 0:
    print("SUCCESS: All ghost contacts are now non-marketing.")
else:
    print(f"WARNING: {remaining} ghost contacts are still marketing.")
```

**Also check email performance**: After 1-2 email sends post-suppression, open rates should improve noticeably because thousands of guaranteed-zero-open contacts have been removed from the send pool.

## Safety Mechanisms

| Mechanism | Detail |
|-----------|--------|
| **CSV audit trail** | Full export with delivery counts, lifecycle stage, and marketing status before any action. |
| **Graduated suppression** | Recommend starting with contacts above your delivery threshold (typically 5-15). Monitor those below it separately. |
| **Overlap detection** | Before State measures how many are already non-marketing from prior processes. |
| **Two-tier list system** | Main list for all ghosts, review list for worst offenders. |
| **Non-destructive** | Suppression, not deletion. CRM records are preserved. |
| **Confirmation prompt** | Present all findings to the user before proceeding. |

## Technical Gotchas

1. **CRITICAL: `NOT_HAS_PROPERTY`, not `EQ 0`.** HubSpot stores "never opened" as a null/absent property. Using `EQ 0` returns nothing. This is the most common mistake with this process.

2. **Search API pagination limit is 10K.** Ghost contacts often exceed 10K. Use segmented queries by delivery volume brackets (1-5, 6-10, 11-20, etc.) to export the complete set. Choose segment boundaries so each segment stays under 10K.

3. **`hs_email_delivered`** is the correct property for delivery count. Do not confuse with `hs_email_sent` (sent but not necessarily delivered) or `num_unique_conversion_events`.

4. **`hs_email_open`** counts total opens, not unique opens. But for ghost contacts, both are null because no open ever occurred.

5. **List API filter for "is unknown"** uses `operationType: "ALL_PROPERTY"` with `operator: "IS_UNKNOWN"`. This is different from the Search API's `NOT_HAS_PROPERTY`.

6. **`hs_marketable_status` is read-only via API.** Same constraint as all suppression skills. Manual UI action or workflow-flag workaround required.

7. **Overlap with hard-bounce and unsubscribe processes**: Some ghost contacts may have already been suppressed. The Before State overlap detection prevents double-counting the billing impact.

## Rollback

- Suppression is reversible: restore contacts to marketing status via the UI or a workflow.
- If ghosts were deleted rather than suppressed, deleted contacts are recoverable for 90 days via Settings > Data Management > Deleted Objects.

## Setup

Create a `.env` file in the repo root:

```
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx
```

No package install is needed — scripts carry PEP 723 inline metadata and run with [`uv`](https://github.com/astral-sh/uv), which resolves dependencies automatically:

```bash
uv run skills/suppress-ghost-contacts/scripts/before.py
```
