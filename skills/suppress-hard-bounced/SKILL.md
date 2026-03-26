---
name: suppress-hard-bounced
description: >
  Identify and suppress hard-bounced contacts to protect email sender
  reputation. Hybrid approach: API for discovery and audit, manual UI
  for suppression (hs_marketable_status is read-only via API).
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: database-hygiene
---

# Suppress Hard-Bounced Contacts

## Purpose

Hard-bounced contacts have permanently undeliverable email addresses. Every email sent to them fails, wastes send volume, and actively damages sender reputation with ISPs like Gmail, Microsoft, and Yahoo. This skill identifies all hard-bounced contacts, exports an audit trail, creates a HubSpot active list for ongoing monitoring, and guides the user through manual suppression in the UI.

## Prerequisites

- A HubSpot private app access token with `crm.objects.contacts.read` and `crm.lists.read`/`crm.lists.write` scopes
- Python 3.10+ with `uv` for package management
- A `.env` file containing `HUBSPOT_ACCESS_TOKEN`
- Super Admin or Marketing Hub Admin permissions for the manual UI suppression step

## Key Constraint

**`hs_marketable_status` is read-only via the API.** You cannot set a contact to non-marketing programmatically. The API is used for discovery, analysis, and audit trail generation. The actual suppression must happen in the HubSpot UI.

## Execution Pattern

This skill follows a 4-stage execution pattern: **Plan -> Before State -> Execute -> After State**.

### Stage 1: Plan

Before writing any code, confirm with the user:

1. **Understand the impact**: Suppressed contacts remain in the CRM but stop counting toward the marketing contact billing tier. They cannot receive marketing emails.
2. **Non-marketing processing timing**: HubSpot processes non-marketing status changes at the start of the next billing cycle. Billing savings are not immediate.
3. **High-bounce contacts**: Contacts with 3+ bounces are the most severe reputation risk. Ask whether the user wants a separate review list for potential deletion.

### Stage 2: Before State

Discover all hard-bounced contacts, break down by bounce reason, and generate an audit CSV.

```python
"""
Before State: Count and audit hard-bounced contacts.
Creates:
  1. A HubSpot active list for ongoing monitoring
  2. A local CSV audit log of all affected contacts
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

# --- Step 1: Paginated search for all hard-bounced contacts ---
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
        "email", "firstname", "lastname",
        "hs_email_hard_bounce_reason_enum",
        "hs_email_bounce", "lifecyclestage",
        "hs_marketable_status", "createdate",
    ],
    "limit": 100,
}

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

    paging = data.get("paging", {})
    after = paging.get("next", {}).get("after")
    if not after:
        break
    time.sleep(0.2)

print(f"Total hard-bounced contacts: {len(all_contacts)}")

# --- Step 2: Bounce reason breakdown ---
reasons = {}
for c in all_contacts:
    r = c["hard_bounce_reason"] or "(empty)"
    reasons[r] = reasons.get(r, 0) + 1

print("\nBounce reason breakdown:")
for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
    pct = (count / len(all_contacts) * 100) if all_contacts else 0
    print(f"  {reason}: {count} ({pct:.1f}%)")

# --- Step 3: Marketing status breakdown ---
already_non_marketing = sum(
    1 for c in all_contacts if c["marketable_status"] == "false"
)
still_marketing = len(all_contacts) - already_non_marketing
print(f"\nAlready non-marketing: {already_non_marketing}")
print(f"Still marketing (need suppression): {still_marketing}")

# --- Step 4: High-bounce contacts (3+) ---
high_bounce = [
    c for c in all_contacts
    if c["bounce_count"] and int(float(c["bounce_count"])) >= 3
]
print(f"Contacts with 3+ bounces (review for deletion): {len(high_bounce)}")

# --- Step 5: Save CSV audit log ---
os.makedirs("data/audit-logs", exist_ok=True)
csv_path = "data/audit-logs/hard-bounced-contacts.csv"

with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "id", "email", "firstname", "lastname", "hard_bounce_reason",
        "bounce_count", "lifecycle_stage", "marketable_status", "createdate",
    ])
    writer.writeheader()
    writer.writerows(all_contacts)

print(f"\nAudit log saved: {csv_path} ({len(all_contacts)} records)")
```

**Expected output**: Total count, bounce reason breakdown, marketing status split, and CSV export.

**Bounce reason categories to explain to the user**:
- **OTHER**: Generic bounce, often a server configuration issue
- **UNKNOWN_USER**: The mailbox does not exist (most common hard bounce)
- **SPAM**: The receiving server flagged the message as spam -- investigate what content was sent
- **POLICY**: Receiving server policy rejected delivery
- **MAILBOX_FULL**: Technically a soft bounce that HubSpot escalated to hard after repeated failures

### Stage 3: Execute

This is a **hybrid step** -- the API creates a HubSpot list, but suppression must happen in the UI.

**Step 3a: Create a HubSpot active list via API**

```python
"""
Execute (API part): Create a HubSpot active list for hard-bounced contacts.
"""
list_payload = {
    "name": "CLEANUP: Hard Bounced Contacts",
    "objectTypeId": "0-1",  # contacts
    "processingType": "DYNAMIC",  # active list
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

resp = requests.post(
    f"{BASE}/crm/v3/lists", headers=headers, json=list_payload,
)

if resp.status_code in (200, 201):
    list_data = resp.json()
    list_id = list_data.get("listId") or list_data.get("list", {}).get("listId")
    print(f"List created! ID: {list_id}")
elif resp.status_code == 409:
    print("List already exists (409 conflict). Use the existing list.")
else:
    print(f"Failed to create list: {resp.status_code} — {resp.text[:300]}")
```

**Step 3b: Suppress contacts in HubSpot UI**

Instruct the user to perform these steps manually:

1. Open the list **"CLEANUP: Hard Bounced Contacts"** in HubSpot
2. Click the **checkbox** in the table header row to select all contacts on the page
3. Click the **"Select all N contacts in this list"** link in the blue banner
4. Click **More** > **Set marketing contact status**
5. Select **Set as non-marketing contact**
6. Click **Confirm**

**Step 3c (optional): Create a high-bounce review list**

If the user wants to review contacts with 3+ bounces for potential deletion, create a second list:

```python
# Optional: List for contacts with 3+ bounces
review_list_payload = {
    "name": "REVIEW: 3+ Bounces - Possible Delete",
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
                        "property": "hs_email_bounce",
                        "operation": {
                            "operationType": "NUMBER",
                            "operator": "IS_GREATER_THAN",
                            "value": 2,
                        },
                    }
                ],
            }
        ],
        "filters": [],
    },
}
```

### Stage 4: After State

Re-run the Before State query. Compare the `still_marketing` count -- it should be zero (or near zero if new bounces occurred between Before and After).

```python
"""
After State: Verify hard-bounced contacts have been suppressed.
"""
# Re-run the same search and check marketable_status
still_marketing_after = sum(
    1 for c in all_contacts_after if c["marketable_status"] != "false"
)

if still_marketing_after == 0:
    print("SUCCESS: All hard-bounced contacts are now non-marketing.")
else:
    print(f"WARNING: {still_marketing_after} hard-bounced contacts "
          f"are still marketing. Re-check the list in the UI.")
```

**Important**: Always re-measure before executing. Counts drift over time as new emails bounce.

## Safety Mechanisms

| Mechanism | Detail |
|-----------|--------|
| **CSV audit trail** | Every hard-bounced contact is exported with full details before any action. |
| **Active list for monitoring** | The HubSpot list is DYNAMIC, so new hard bounces are automatically captured. Keep it active permanently. |
| **Non-destructive suppression** | Contacts are moved to non-marketing status, not deleted. They remain in the CRM with full history. |
| **Separate review list** | Contacts with 3+ bounces are flagged in a dedicated list for deletion review, not auto-deleted. |
| **Confirmation prompt** | Present Before State findings to the user and wait for explicit confirmation before creating lists or instructing UI actions. |

## Technical Gotchas

1. **Property name is `hs_email_hard_bounce_reason_enum`**, not `hs_email_hard_bounce_reason`. The `_enum` suffix is required in API calls.

2. **`hs_marketable_status` is read-only via API.** This is the single biggest constraint. There is no API endpoint to change a contact's marketing status. The only way is through the HubSpot UI or via a HubSpot workflow triggered by a custom property flag.

3. **Workaround for full automation**: Create a custom contact property (e.g., `suppress_marketing_flag`), set it via API, then build a HubSpot workflow that triggers on that flag to set the contact as non-marketing. This adds complexity but enables end-to-end automation.

4. **Billing cycle timing**: Non-marketing status changes take effect at the start of the next billing cycle. Do not expect immediate billing savings.

5. **Bounce count property**: `hs_email_bounce` stores the count as a string that may contain decimal values (e.g., `"3.0"`). Always cast with `int(float(value))`.

6. **Keep the list active permanently.** New hard bounces will occur over time. The active list captures them automatically. Run this suppression process monthly or set up a workflow.

## Package Setup

```bash
uv init hubspot-cleanup
cd hubspot-cleanup
uv add requests python-dotenv
```

Create a `.env` file:
```
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx
```
