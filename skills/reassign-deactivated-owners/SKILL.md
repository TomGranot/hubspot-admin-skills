---
name: reassign-deactivated-owners
description: >
  Reassign contacts and companies from deactivated team members to active
  owners. Fully automated via the HubSpot Owners API and Batch Update API.
  Includes territory analysis for informed reassignment decisions.
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: database-hygiene
---

# Reassign Contacts From Deactivated Owners

## Purpose

When team members leave an organization, their HubSpot-owned contacts and companies become orphaned. Leads are not being worked, accounts are not being managed, and any automation that relies on Contact owner or Company owner routes to dead ends. This skill identifies deactivated owners, analyzes their contact portfolios, and batch-reassigns ownership via the API.

## Prerequisites

- A HubSpot private app access token with `crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.objects.companies.read`, `crm.objects.companies.write`, and `crm.objects.owners.read` scopes
- Python 3.10+ with `uv` for package management
- A `.env` file containing `HUBSPOT_ACCESS_TOKEN`
- A decision from team leadership on the reassignment strategy (see Plan stage)

## CRITICAL: Retrieving Deactivated Owners

The Owners API requires the `archived=true` parameter to retrieve deactivated users. The default endpoint only returns active owners. This is the most commonly missed detail.

```python
# CORRECT - returns deactivated/archived owners
requests.get(f"{BASE}/crm/v3/owners", headers=headers,
             params={"limit": 500, "archived": "true"})

# DEFAULT - returns only active owners
requests.get(f"{BASE}/crm/v3/owners", headers=headers,
             params={"limit": 500})
```

Deactivated owners have `"archived": true` in their response object.

## Interview: Gather Requirements

Before executing, collect the following information from the user:

**Q1: Who should contacts from [deactivated user X] be reassigned to?**
- Run the Before State script first to identify deactivated users and their contact counts, then ask this question for each deactivated user found
- Examples: "Assign Jane Doe's 500 contacts to John Smith", "Distribute evenly across the sales team", "Assign all to the Marketing Team user"
- Default: No default -- this requires an explicit business decision for each deactivated user

**Q2: Should unowned contacts be assigned to a default user? If so, who?**
- Examples: "Yes, assign to our Integration User", "Yes, round-robin across the sales team", "No, leave them unowned for now"
- Default: No -- unowned contacts are a separate strategic decision from deactivated-owner contacts

## Execution Pattern

This skill follows a 4-stage execution pattern: **Plan -> Before State -> Execute -> After State**.

### Stage 1: Plan

Before writing any code, confirm with the user:

1. **Reassignment strategy** -- one of three options:
   - **Option A (Unassign)**: Set owner to blank. Best if no one is actively working these contacts and the team wants to start fresh with new assignment rules.
   - **Option B (Distribute to active team members)**: Round-robin across current reps. Best if there are active reps who should work these leads.
   - **Option C (Assign to shared owner)**: Assign to a single placeholder user (e.g., "Integration User" or "Marketing Team"). Good middle ground.

2. **Territory analysis**: Before reassigning, the user may want to analyze the portfolio of each deactivated owner (customer %, lifecycle distribution, industry breakdown) to make informed decisions about who gets which contacts.

3. **Unassigned contacts**: Ask whether the user also wants to address contacts that have no owner at all. This is a separate strategic decision.

4. **Preserve historical ownership**: Ask whether to create a "Previous Owner" custom property to retain a record of the original assignment.

### Stage 2: Before State

Discover all deactivated owners and analyze their contact/company portfolios.

```python
"""
Before State: Identify deactivated owners and their contact/company counts.
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

# --- Step 1: Get all owners (active + deactivated) ---
print("Fetching owners...")

# Active owners
resp_active = requests.get(
    f"{BASE}/crm/v3/owners", headers=headers, params={"limit": 500},
)
resp_active.raise_for_status()
active_owners = resp_active.json().get("results", [])

# CRITICAL: Use archived=true for deactivated owners
resp_archived = requests.get(
    f"{BASE}/crm/v3/owners", headers=headers,
    params={"limit": 500, "archived": "true"},
)
resp_archived.raise_for_status()
deactivated_owners = resp_archived.json().get("results", [])

print(f"Active owners: {len(active_owners)}")
print(f"Deactivated owners: {len(deactivated_owners)}")

print("\nActive owners:")
for o in active_owners:
    print(f"  {o.get('firstName', '')} {o.get('lastName', '')} "
          f"({o.get('email', '')}) -- ID: {o['id']}")

print("\nDeactivated owners:")
for o in deactivated_owners:
    print(f"  {o.get('firstName', '')} {o.get('lastName', '')} "
          f"({o.get('email', '')}) -- ID: {o['id']}")

# --- Step 2: Count contacts per deactivated owner ---
print("\nCounting contacts per deactivated owner...")

url = f"{BASE}/crm/v3/objects/contacts/search"
deactivated_contact_data = {}
total_deactivated_contacts = 0

for o in deactivated_owners:
    owner_id = o["id"]
    name = f"{o.get('firstName', '')} {o.get('lastName', '')}"
    resp = requests.post(url, headers=headers, json={
        "filterGroups": [{"filters": [
            {"propertyName": "hubspot_owner_id", "operator": "EQ",
             "value": str(owner_id)},
        ]}],
        "limit": 1,
    })
    if resp.status_code == 200:
        count = resp.json().get("total", 0)
        deactivated_contact_data[name] = {
            "id": owner_id, "email": o.get("email", ""), "contacts": count,
        }
        total_deactivated_contacts += count
        if count > 0:
            print(f"  {name}: {count} contacts")
    time.sleep(0.1)

print(f"\nTotal contacts owned by deactivated users: {total_deactivated_contacts}")

# --- Step 3: Count unassigned contacts ---
print("\nCounting unassigned contacts (no owner)...")

resp_no_owner = requests.post(url, headers=headers, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hubspot_owner_id", "operator": "NOT_HAS_PROPERTY"},
    ]}],
    "limit": 1,
})
resp_no_owner.raise_for_status()
unassigned_contacts = resp_no_owner.json().get("total", 0)
print(f"Unassigned contacts: {unassigned_contacts}")

# --- Step 4: Count companies per deactivated owner ---
print("\nCounting companies per deactivated owner...")

comp_url = f"{BASE}/crm/v3/objects/companies/search"
total_deactivated_companies = 0

for o in deactivated_owners:
    owner_id = o["id"]
    name = f"{o.get('firstName', '')} {o.get('lastName', '')}"
    resp = requests.post(comp_url, headers=headers, json={
        "filterGroups": [{"filters": [
            {"propertyName": "hubspot_owner_id", "operator": "EQ",
             "value": str(owner_id)},
        ]}],
        "limit": 1,
    })
    if resp.status_code == 200:
        count = resp.json().get("total", 0)
        total_deactivated_companies += count
        if count > 0:
            print(f"  {name}: {count} companies")
    time.sleep(0.1)

print(f"\nTotal companies owned by deactivated users: {total_deactivated_companies}")

# --- Step 5: Save CSV audit log ---
os.makedirs("data/audit-logs", exist_ok=True)
csv_path = "data/audit-logs/ownership-summary.csv"

with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "owner_name", "owner_id", "email", "status", "contacts", "companies",
    ])
    writer.writeheader()
    for o in deactivated_owners:
        name = f"{o.get('firstName', '')} {o.get('lastName', '')}"
        data = deactivated_contact_data.get(name, {})
        writer.writerow({
            "owner_name": name,
            "owner_id": o["id"],
            "email": o.get("email", ""),
            "status": "deactivated",
            "contacts": data.get("contacts", 0),
            "companies": 0,  # Would need per-owner company count
        })
    for o in active_owners:
        name = f"{o.get('firstName', '')} {o.get('lastName', '')}"
        writer.writerow({
            "owner_name": name,
            "owner_id": o["id"],
            "email": o.get("email", ""),
            "status": "active",
            "contacts": "",
            "companies": "",
        })

print(f"\nAudit CSV saved: {csv_path}")
```

**Optional: Territory analysis template**

For informed reassignment decisions, generate a portfolio breakdown for each deactivated owner:

```python
# Territory analysis: lifecycle + industry breakdown per owner
for o in deactivated_owners:
    owner_id = o["id"]
    name = f"{o.get('firstName', '')} {o.get('lastName', '')}"
    print(f"\n--- Portfolio: {name} ---")

    # Lifecycle breakdown
    for stage in ["customer", "opportunity", "salesqualifiedlead",
                   "marketingqualifiedlead", "lead", "subscriber"]:
        resp = requests.post(url, headers=headers, json={
            "filterGroups": [{"filters": [
                {"propertyName": "hubspot_owner_id", "operator": "EQ",
                 "value": str(owner_id)},
                {"propertyName": "lifecyclestage", "operator": "EQ",
                 "value": stage},
            ]}],
            "limit": 1,
        })
        if resp.status_code == 200:
            count = resp.json().get("total", 0)
            if count > 0:
                print(f"  {stage}: {count}")
        time.sleep(0.1)
```

**Present findings to the user.** Ask for explicit reassignment instructions (which deactivated owner's contacts go to which active owner or shared user).

### Stage 3: Execute

Batch-reassign contacts and companies from deactivated owners to the target owner(s).

```python
"""
Execute: Batch-reassign contacts from deactivated owners.
"""
import time
import requests

# Target owner ID (get from user after Before State)
TARGET_OWNER_ID = "REPLACE_WITH_TARGET_OWNER_ID"


def get_contact_ids_for_owner(owner_id, limit=100):
    """
    Get contact IDs for a given owner using pagination.
    HubSpot search API caps at 10K results per query.
    For larger sets, the caller should loop until no more
    contacts remain for this owner.
    """
    contact_ids = []
    after = None
    while True:
        payload = {
            "filterGroups": [{"filters": [
                {"propertyName": "hubspot_owner_id", "operator": "EQ",
                 "value": str(owner_id)},
            ]}],
            "properties": ["email"],
            "limit": limit,
        }
        if after:
            payload["after"] = after

        resp = requests.post(
            f"{BASE}/crm/v3/objects/contacts/search",
            headers=headers, json=payload,
        )
        if resp.status_code == 400:
            # Hit the 10K search limit -- return what we have
            break
        resp.raise_for_status()

        data = resp.json()
        results = data.get("results", [])
        if not results:
            break

        contact_ids.extend(c["id"] for c in results)

        paging = data.get("paging", {})
        if paging.get("next"):
            after = paging["next"]["after"]
            time.sleep(0.2)
        else:
            break

    return contact_ids


def batch_update_owner(contact_ids, new_owner_id):
    """Update contact owner in batches of 100."""
    success = 0
    failed = 0

    for i in range(0, len(contact_ids), 100):
        batch = contact_ids[i : i + 100]
        payload = {
            "inputs": [
                {"id": cid, "properties": {"hubspot_owner_id": new_owner_id}}
                for cid in batch
            ]
        }

        resp = requests.post(
            f"{BASE}/crm/v3/objects/contacts/batch/update",
            headers=headers, json=payload,
        )
        if resp.status_code == 200:
            success += len(batch)
        else:
            failed += len(batch)
            print(f"  Batch failed: {resp.status_code} -- {resp.text[:200]}")

        time.sleep(0.5)

    return success, failed


# --- Main execution loop ---
total_success = 0
total_failed = 0

for o in deactivated_owners:
    owner_id = o["id"]
    name = f"{o.get('firstName', '')} {o.get('lastName', '')}"

    # Count remaining contacts for this owner
    resp = requests.post(url, headers=headers, json={
        "filterGroups": [{"filters": [
            {"propertyName": "hubspot_owner_id", "operator": "EQ",
             "value": str(owner_id)},
        ]}],
        "limit": 1,
    })
    count = resp.json().get("total", 0)
    if count == 0:
        continue

    print(f"\nProcessing: {name} ({count} contacts)...")
    owner_success = 0
    owner_failed = 0
    pass_num = 0

    # Loop because search API caps at 10K -- need multiple passes
    # for owners with >10K contacts
    while True:
        pass_num += 1
        contact_ids = get_contact_ids_for_owner(owner_id)
        if not contact_ids:
            break

        print(f"  Pass {pass_num}: fetched {len(contact_ids)} contact IDs")
        s, f = batch_update_owner(contact_ids, TARGET_OWNER_ID)
        owner_success += s
        owner_failed += f
        print(f"  Updated: {s}, Failed: {f}")

        if f > 0:
            break  # Stop if hitting errors
        time.sleep(1)

    total_success += owner_success
    total_failed += owner_failed
    print(f"  Total for {name}: {owner_success} updated, {owner_failed} failed")

print(f"\nTotal reassigned: {total_success}")
print(f"Total failed: {total_failed}")
```

**For companies, use the same pattern** with the companies endpoint:

```python
# Batch update company owner
payload = {
    "inputs": [
        {"id": company_id, "properties": {"hubspot_owner_id": new_owner_id}}
        for company_id in batch
    ]
}
resp = requests.post(
    f"{BASE}/crm/v3/objects/companies/batch/update",
    headers=headers, json=payload,
)
```

### Stage 4: After State

Verify that no contacts or companies remain assigned to deactivated owners.

```python
"""
After State: Verify all deactivated owner contacts are reassigned.
"""
for o in deactivated_owners:
    owner_id = o["id"]
    name = f"{o.get('firstName', '')} {o.get('lastName', '')}"

    # Check contacts
    resp = requests.post(url, headers=headers, json={
        "filterGroups": [{"filters": [
            {"propertyName": "hubspot_owner_id", "operator": "EQ",
             "value": str(owner_id)},
        ]}],
        "limit": 1,
    })
    remaining = resp.json().get("total", 0)
    if remaining == 0:
        print(f"  {name}: 0 contacts remaining (OK)")
    else:
        print(f"  {name}: {remaining} contacts still assigned (INVESTIGATE)")

    # Check companies
    resp_c = requests.post(comp_url, headers=headers, json={
        "filterGroups": [{"filters": [
            {"propertyName": "hubspot_owner_id", "operator": "EQ",
             "value": str(owner_id)},
        ]}],
        "limit": 1,
    })
    remaining_c = resp_c.json().get("total", 0)
    if remaining_c == 0:
        print(f"  {name}: 0 companies remaining (OK)")
    else:
        print(f"  {name}: {remaining_c} companies still assigned (INVESTIGATE)")

    time.sleep(0.1)
```

## Safety Mechanisms

| Mechanism | Detail |
|-----------|--------|
| **CSV audit trail** | Full ownership summary exported before any changes. |
| **Territory analysis** | Optional portfolio breakdown (lifecycle, industry) for each deactivated owner to inform reassignment decisions. |
| **Human decision required** | The target owner ID must be explicitly provided by the user. The skill never auto-decides where to reassign. |
| **Multi-pass loop** | Handles owners with >10K contacts by looping until all are reassigned (search API caps at 10K per query). |
| **Error handling** | Batch update stops processing an owner if failures occur, preventing cascading errors. |
| **Previous Owner property** | Recommend creating a custom property to preserve historical ownership before reassignment. |

## Technical Gotchas

1. **CRITICAL: `archived=true` for deactivated owners.** The Owners API default endpoint only returns active owners. You must pass `archived=true` as a query parameter to retrieve deactivated/archived users. Without this, you will see zero deactivated owners and incorrectly conclude the data is clean.

2. **Search API caps at 10K results.** For deactivated owners with more than 10,000 contacts, a single search query cannot return all IDs. Use a multi-pass approach: fetch up to 10K IDs, batch-update them, then search again (the updated contacts no longer match the filter, so the next 10K become available).

3. **Batch update endpoint**: `POST /crm/v3/objects/contacts/batch/update` accepts up to 100 inputs per call and returns HTTP 200 on success (unlike batch archive which returns 204).

4. **Owner ID is a string in filters.** When filtering by `hubspot_owner_id`, pass the value as a string even though it looks numeric: `"value": str(owner_id)`.

5. **Deactivated users may not appear in UI filter dropdowns.** Some HubSpot UI versions hide deactivated users from the Contact Owner filter. Use the API approach instead.

6. **Rate limiting**: Use `time.sleep(0.5)` between batch update calls and `time.sleep(0.2)` between search pagination calls. The private app rate limit is approximately 100 requests per 10 seconds.

7. **Handle unassigned contacts separately.** Contacts with no owner at all (`hubspot_owner_id NOT_HAS_PROPERTY`) are a separate population from deactivated-owner contacts. They require a different strategic decision.

8. **Workflow cleanup after reassignment**: Check for any active workflows or sequences that reference deactivated users by name or ID. Update them to reference active users.

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
