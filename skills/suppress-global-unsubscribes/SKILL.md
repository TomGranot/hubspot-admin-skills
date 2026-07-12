---
name: suppress-global-unsubscribes
description: "Identify and suppress globally unsubscribed contacts to ensure legal compliance and reduce billing. Hybrid approach: API for discovery and audit, manual UI for suppression (hs_marketable_status is read-only)."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: database-hygiene
---

# Suppress Globally Unsubscribed Contacts

## Purpose

Contacts who have globally unsubscribed cannot legally be sent marketing emails under CAN-SPAM, GDPR, or CASL. Despite this, they may still be classified as "marketing contacts" in HubSpot, meaning the organization is paying for contacts it cannot and must not email. This skill identifies all globally unsubscribed contacts, analyzes their lifecycle distribution, and guides suppression.

## Prerequisites

- A HubSpot private app access token with `crm.objects.contacts.read` and `crm.lists.read`/`crm.lists.write` scopes
- Python 3.10+ with `uv` for package management
- A `.env` file containing `HUBSPOT_ACCESS_TOKEN`
- Super Admin or Marketing Hub Admin permissions for the manual UI suppression step

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/suppress-global-unsubscribes/scripts/before.py` |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run skills/suppress-global-unsubscribes/scripts/after.py` |

There is no execute script: the marketing-status change itself must happen via a HubSpot workflow or the UI (see Key Constraint and Stage 3).

## Key Constraint

**`hs_marketable_status` is read-only via the API.** The API handles discovery and audit. Actual suppression must happen in the HubSpot UI.

## Execution Pattern

This skill follows a 4-stage execution pattern: **Plan -> Before -> Execute -> After**.

### Stage 1: Plan

Before writing any code, confirm with the user:

1. **Do not re-subscribe anyone.** Even if the unsubscribe pattern looks like a batch import error, re-subscribing contacts without explicit consent violates CAN-SPAM and GDPR.
2. **Billing impact**: Non-marketing status changes take effect at the start of the next billing cycle.
3. **Investigate uniform patterns**: If all subscription types show nearly identical unsubscribe counts, this suggests a batch event (migration, import error, compliance sweep) rather than organic opt-outs. Understanding the origin prevents recurrence.

### Stage 2: Before

Count globally unsubscribed contacts, break down by lifecycle stage, and generate an audit CSV.

```python
"""
Before State: Count globally unsubscribed contacts.
Note: >10K results means the Search API pagination limit may apply.
Uses count-only queries and segmented exports.
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

# --- Step 1: Total count ---
resp = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_email_optout", "operator": "EQ", "value": "true"}
    ]}],
    "limit": 1,
})
resp.raise_for_status()
total_unsubscribed = resp.json().get("total", 0)
print(f"Total globally unsubscribed: {total_unsubscribed}")

# --- Step 2: How many are still marketing? ---
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

print(f"Still marketing (need suppression): {still_marketing}")
print(f"Already non-marketing: {already_non_marketing}")

# --- Step 3: Lifecycle stage breakdown ---
print("\nLifecycle stage breakdown:")
stages = [
    "lead", "subscriber", "marketingqualifiedlead",
    "salesqualifiedlead", "opportunity", "customer",
    "evangelist", "other",
]

for stage in stages:
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
    time.sleep(0.1)

# Check contacts with no lifecycle stage
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
```

**CRITICAL: API pagination limit.** The HubSpot CRM Search API caps at 10,000 results per query. For larger sets, use segmented queries to get complete exports.

```python
# --- Step 4: Export CSV using segmented queries ---
# If total > 10K, segment by lifecycle stage to bypass the pagination cap.

PROPS = [
    "email", "firstname", "lastname", "hs_email_optout",
    "hs_marketable_status", "lifecyclestage", "createdate",
]

all_contacts = []

if total_unsubscribed <= 10000:
    # Simple pagination
    segments = [(None, None)]  # No lifecycle filter needed
else:
    # Segment by lifecycle stage to keep each under 10K
    segments = [
        ("lifecyclestage", "lead"),
        ("lifecyclestage", "subscriber"),
        ("lifecyclestage", "marketingqualifiedlead"),
        ("lifecyclestage", "salesqualifiedlead"),
        ("lifecyclestage", "opportunity"),
        ("lifecyclestage", "customer"),
        ("lifecyclestage", "evangelist"),
        ("lifecyclestage", "other"),
        ("lifecyclestage", None),  # NOT_HAS_PROPERTY
    ]

for seg_prop, seg_value in segments:
    after = None
    seg_filters = [
        {"propertyName": "hs_email_optout", "operator": "EQ", "value": "true"},
    ]
    if seg_prop and seg_value:
        seg_filters.append(
            {"propertyName": seg_prop, "operator": "EQ", "value": seg_value}
        )
    elif seg_prop and seg_value is None:
        seg_filters.append(
            {"propertyName": seg_prop, "operator": "NOT_HAS_PROPERTY"}
        )

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
                "unsubscribed": props.get("hs_email_optout", ""),
                "marketable_status": props.get("hs_marketable_status", ""),
                "lifecycle_stage": props.get("lifecyclestage", ""),
                "createdate": props.get("createdate", ""),
            })

        paging = data.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after:
            break
        time.sleep(0.15)

# Save CSV
os.makedirs("data/audit-logs", exist_ok=True)
csv_path = "data/audit-logs/globally-unsubscribed-contacts.csv"

with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "id", "email", "firstname", "lastname",
        "unsubscribed", "marketable_status", "lifecycle_stage", "createdate",
    ])
    writer.writeheader()
    writer.writerows(all_contacts)

print(f"\nAudit CSV saved: {csv_path} ({len(all_contacts)} records)")
if len(all_contacts) < total_unsubscribed:
    print(f"Warning: {total_unsubscribed - len(all_contacts)} contacts "
          f"not captured (pagination limits)")
```

**Present findings to the user** before proceeding. Key data points:
- Total unsubscribed contacts
- How many are still billed as marketing (this is the actionable number)
- Lifecycle breakdown (are any customers unsubscribed? That warrants investigation)

### Stage 3: Execute

**Step 3a: Create a HubSpot active list via API**

```python
"""
Execute (API part): Create a HubSpot active list for unsubscribed contacts.
"""
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
    print(f"Failed: {resp.status_code} — {resp.text[:300]}")
```

**Step 3b: Suppress contacts in HubSpot UI**

Instruct the user to perform these steps manually:

1. Open the list **"CLEANUP: Globally Unsubscribed"** in HubSpot
2. Click the **checkbox** in the table header row
3. Click **"Select all N contacts in this list"** in the blue banner
4. Click **More** > **Set marketing contact status**
5. Select **Set as non-marketing contact**
6. Click **Confirm**
7. For large lists (10K+), HubSpot may process this in batches over several minutes

**Step 3c: Keep the list active permanently**

Do NOT delete this list. It is DYNAMIC and will automatically capture future unsubscribes. Recommend running this suppression process monthly or setting up a HubSpot workflow:
- Trigger: `Unsubscribed from all email` is equal to `True`
- Action: Set marketing contact status to non-marketing

### Stage 4: After

Re-run the Before State marketing status query. The `still_marketing` count should be zero.

```python
"""
After State: Verify unsubscribed contacts are suppressed.
"""
resp = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_email_optout", "operator": "EQ", "value": "true"},
        {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
    ]}],
    "limit": 1,
})
resp.raise_for_status()
remaining = resp.json().get("total", 0)

if remaining == 0:
    print("SUCCESS: All globally unsubscribed contacts are non-marketing.")
else:
    print(f"WARNING: {remaining} unsubscribed contacts are still marketing.")
```

## Safety Mechanisms

| Mechanism | Detail |
|-----------|--------|
| **CSV audit trail** | Full export of all unsubscribed contacts before any action. |
| **Lifecycle breakdown** | Surfaces unsubscribed customers for investigation before suppression. |
| **Non-destructive** | Contacts are set to non-marketing, not deleted. CRM data is preserved. |
| **Active list** | DYNAMIC list captures future unsubscribes automatically. |
| **Confirmation prompt** | Always present findings and wait for explicit user confirmation. |

## Technical Gotchas

1. **API pagination limit is 10K contacts.** The HubSpot CRM Search API cannot return more than 10,000 results per query, even with pagination. For datasets larger than 10K, use segmented queries -- add a secondary filter (lifecycle stage, create date range, etc.) to break the set into chunks under 10K each.

2. **`hs_email_optout` is the correct property.** The filter is `hs_email_optout EQ true`. Do not confuse with subscription-type-specific opt-outs (e.g., `hs_email_optout_<ID>`), which are per-subscription.

3. **List API filter syntax differs from Search API.** The Lists API uses `operationType: "ENUMERATION"` with `operator: "IS_EQUAL_TO"`, while the Search API uses `operator: "EQ"`. These are different APIs with different schemas.

4. **Uniform unsubscribe patterns are suspicious.** If all subscription types show nearly identical counts, it indicates a batch event (import, migration, compliance sweep) rather than organic opt-outs. Flag this for the user.

5. **Do not re-subscribe contacts.** Even if a batch unsubscribe was an error, the only legally compliant path is to contact them through a non-email channel and ask them to re-subscribe via an opt-in form.

6. **`hs_marketable_status` is read-only via API.** Same constraint as suppress-hard-bounced. See that skill's gotchas for the custom-property-flag workaround.

## Rollback

- Setting contacts back to marketing status is possible in the UI, but a globally unsubscribed contact must re-opt-in before receiving marketing email — do not circumvent consent.
- The before CSV records every affected contact.

## Setup

Create a `.env` file in the repo root:

```
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx
```

No package install is needed — scripts carry PEP 723 inline metadata and run with [`uv`](https://github.com/astral-sh/uv), which resolves dependencies automatically:

```bash
uv run skills/suppress-global-unsubscribes/scripts/before.py
```
