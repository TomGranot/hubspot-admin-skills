---
name: delete-no-email-contacts
description: >
  Delete contacts with no email address from a HubSpot CRM instance.
  These contacts cannot receive any communication and inflate billing.
  Fully automated via the HubSpot CRM Search and Batch Archive APIs.
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: database-hygiene
---

# Delete Contacts With No Email Address

## Purpose

Contacts without an email address serve no functional purpose in a HubSpot Marketing Hub instance. They cannot receive marketing emails, sales sequences, or transactional messages. They inflate the billed contact count. This skill identifies and deletes them via the API.

## Prerequisites

- A HubSpot private app access token with `crm.objects.contacts.read` and `crm.objects.contacts.write` scopes
- Python 3.10+ with `uv` for package management
- A `.env` file containing `HUBSPOT_ACCESS_TOKEN`

## Execution Pattern

This skill follows a 4-stage execution pattern: **Plan -> Before State -> Execute -> After State**.

### Stage 1: Plan

Before writing any code, confirm these items with the user:

1. **Root cause**: Ask whether any integrations (CRM sync, form tool, import process) are intentionally creating contacts without email. If so, fix the inflow first.
2. **Threshold**: The default safety abort threshold is 500 contacts. If the user expects more, adjust the threshold in the execute script.
3. **Recovery window**: Confirm the user understands that deleted contacts are recoverable for 90 days via HubSpot Settings > Data Management > Deleted Objects.

### Stage 2: Before State

Run a count query to establish the baseline. Save results for comparison.

```python
"""
Before State: Count contacts with no email address.
"""
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

search_payload = {
    "filterGroups": [
        {
            "filters": [
                {
                    "propertyName": "email",
                    "operator": "NOT_HAS_PROPERTY",
                }
            ]
        }
    ],
    "properties": ["firstname", "lastname", "createdate", "hs_object_id"],
    "limit": 1,  # Only need the total count
}

url = f"{BASE}/crm/v3/objects/contacts/search"
response = requests.post(url, headers=headers, json=search_payload)
response.raise_for_status()

data = response.json()
total = data.get("total", 0)

print(f"BEFORE STATE: {total} contacts exist with no email address.")

if total > 0 and data.get("results"):
    sample = data["results"][0]
    props = sample.get("properties", {})
    print(f"  Sample: ID {sample['id']}, "
          f"{props.get('firstname', '(empty)')} {props.get('lastname', '(empty)')}, "
          f"created {props.get('createdate', '(unknown)')}")
```

**Expected output**: A count of contacts with no email and a sample record for sanity checking.

**Present findings to the user** before proceeding. Ask for explicit confirmation to continue.

### Stage 3: Execute

Collect all contact IDs via paginated search, export a CSV audit trail, then batch-delete.

```python
"""
Execute: Delete all contacts with no email address.
Steps:
  1. Paginated search to collect all contact IDs
  2. Export CSV audit log before deletion
  3. Batch archive in groups of 100
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

# --- Step 1: Collect all contact IDs ---
all_contacts = []
after = None

search_payload = {
    "filterGroups": [
        {
            "filters": [
                {
                    "propertyName": "email",
                    "operator": "NOT_HAS_PROPERTY",
                }
            ]
        }
    ],
    "properties": ["firstname", "lastname", "createdate", "hs_object_id"],
    "limit": 100,
}

while True:
    payload = search_payload.copy()
    if after:
        payload["after"] = after

    resp = requests.post(
        f"{BASE}/crm/v3/objects/contacts/search",
        headers=headers, json=payload,
    )
    resp.raise_for_status()
    data = resp.json()

    for contact in data.get("results", []):
        props = contact.get("properties", {})
        all_contacts.append({
            "id": contact["id"],
            "firstname": props.get("firstname", ""),
            "lastname": props.get("lastname", ""),
            "createdate": props.get("createdate", ""),
        })

    paging = data.get("paging", {})
    after = paging.get("next", {}).get("after")
    if not after:
        break
    time.sleep(0.2)  # Rate limiting

print(f"Total contacts to delete: {len(all_contacts)}")

# --- Step 2: SAFETY CHECK ---
ABORT_THRESHOLD = 500
if len(all_contacts) > ABORT_THRESHOLD:
    print(f"SAFETY ABORT: Found {len(all_contacts)} contacts, "
          f"exceeds threshold of {ABORT_THRESHOLD}.")
    print("Review the data and adjust the threshold if this is expected.")
    exit(1)

# --- Step 3: Export CSV audit trail ---
os.makedirs("data/audit-logs", exist_ok=True)
csv_path = "data/audit-logs/deleted-no-email-contacts.csv"

with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["id", "firstname", "lastname", "createdate"])
    writer.writeheader()
    writer.writerows(all_contacts)

print(f"Audit log saved: {csv_path} ({len(all_contacts)} records)")

# --- Step 4: Batch delete ---
all_ids = [c["id"] for c in all_contacts]
BATCH_SIZE = 100
deleted_count = 0
failed_ids = []

for i in range(0, len(all_ids), BATCH_SIZE):
    batch = all_ids[i : i + BATCH_SIZE]
    delete_payload = {"inputs": [{"id": cid} for cid in batch]}

    resp = requests.post(
        f"{BASE}/crm/v3/objects/contacts/batch/archive",
        headers=headers, json=delete_payload,
    )

    if resp.status_code == 204:
        deleted_count += len(batch)
        print(f"  Batch {i // BATCH_SIZE + 1}: deleted {len(batch)} contacts")
    else:
        failed_ids.extend(batch)
        print(f"  Batch FAILED: {resp.status_code} — {resp.text[:200]}")

    time.sleep(0.5)  # Rate limiting between batches

print(f"\nDeleted: {deleted_count}, Failed: {len(failed_ids)}")
```

**Key API details**:
- `POST /crm/v3/objects/contacts/search` with `NOT_HAS_PROPERTY` filter on `email`
- Paginate with `after` cursor, 100 results per page
- `POST /crm/v3/objects/contacts/batch/archive` accepts up to 100 IDs per call
- Successful archive returns HTTP 204 (no content)

### Stage 4: After State

Re-run the before-state query to confirm zero contacts remain.

```python
"""
After State: Verify no contacts with missing email remain.
"""
# (Same search payload as Before State)
response = requests.post(url, headers=headers, json=search_payload)
response.raise_for_status()
total = response.json().get("total", 0)

if total == 0:
    print("SUCCESS: 0 contacts with no email remain.")
else:
    print(f"WARNING: {total} contacts with no email still exist.")
    print("New contacts may have been created since deletion. Investigate.")
```

**Present results to the user.** If new contacts appeared, investigate the source (form submissions, integrations, imports).

## Safety Mechanisms

| Mechanism | Detail |
|-----------|--------|
| **Abort threshold** | Hard-coded at 500 contacts by default. If the search returns more, the script exits without deleting anything. Adjust only with explicit user confirmation. |
| **CSV audit trail** | Every contact ID, name, and create date is exported to CSV before any deletion occurs. |
| **Confirmation prompt** | Always present the Before State count to the user and wait for explicit confirmation before running Execute. |
| **90-day recovery** | Deleted contacts can be restored via HubSpot Settings > Data Management > Deleted Objects for 90 days. |
| **Archived contacts audit** | After deletion, you can retrieve deleted contacts via the standard contacts endpoint with `archived=true` parameter to verify what was removed. |

## Technical Gotchas

1. **`NOT_HAS_PROPERTY` vs `EQ ""`**: Use `NOT_HAS_PROPERTY` operator, not `EQ` with an empty string. HubSpot treats "property not set" differently from "property set to empty string."

2. **Search API pagination limit**: The HubSpot CRM Search API has a hard cap of 10,000 results per query. For this use case (typically a few hundred contacts), this is not an issue. If you encounter it, use segmented queries (e.g., filter by create date ranges).

3. **Rate limiting**: The search API allows ~4 requests/second for a private app. The batch archive API is more restrictive. Use `time.sleep(0.5)` between batch archive calls.

4. **Batch archive returns 204**: A successful batch archive returns HTTP 204 with an empty body, not 200. Check for `status_code == 204`.

5. **Contacts may reappear**: If an integration or form is creating contacts without email, new ones will appear after deletion. Always investigate the root cause.

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
