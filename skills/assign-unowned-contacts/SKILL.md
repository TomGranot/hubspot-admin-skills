---
name: assign-unowned-contacts
description: "Assign an owner to marketing contacts that have no owner. Ensures every marketable contact has accountability for follow-up, proper lead routing, and accurate owner-based reporting."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: data-enrichment
---

# Assign Unowned Marketing Contacts

Assign an owner to all marketing contacts that currently have no owner. Unowned contacts create gaps in reporting, prevent proper lead routing, and mean no one is accountable for follow-up on marketing-generated responses.

## Why This Matters

Marketing contacts without an owner are a blind spot. They receive campaigns but no one sees their responses. They appear in aggregate metrics but not in individual pipeline views. In owner-based dashboards and reports, they simply do not exist. For teams using round-robin or territory-based routing, unowned contacts bypass the entire system.

## Prerequisites

- Phase 1 hygiene and earlier Phase 3 enrichment processes completed
- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with contact read/write and owners read scopes
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- Access to Contacts with permission to bulk edit owner assignments
- **Approval from team leads before bulk assignment.** This is a business decision, not just a technical one. Get sign-off on the assignment strategy before proceeding.

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/assign-unowned-contacts/scripts/before.py` |
| Execute | [`scripts/execute.py`](./scripts/execute.py) | `uv run skills/assign-unowned-contacts/scripts/execute.py` |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run skills/assign-unowned-contacts/scripts/after.py` |

`before.py` counts unowned marketing contacts and lists available owners. `execute.py` batch-assigns them to `HUBSPOT_TARGET_OWNER_ID` (set in `.env`; safety threshold 50,000 — high because owner assignment is fully reversible). `after.py` verifies the count dropped to zero.

## Interview: Gather Requirements

Before executing, collect the following information from the user:

**Q1: Who should unowned contacts be assigned to?**
- Examples: "Assign all to our Integration User", "Distribute across the sales team", "Assign to the Marketing Team user", "Assign to specific reps by territory"
- Default: No default -- this is a business decision that requires team lead approval

**Q2: Should we use territory-based routing, round-robin, or a single catch-all owner?**
- Examples: Territory-based (assign by geography or industry), round-robin (distribute evenly across active reps), catch-all (assign all to one user)
- Default: Catch-all to a single integration/service user as a temporary measure, with plans to implement proper routing later

## Plan

1. Identify all marketing contacts with no owner (before state)
2. Decide on the assignment strategy (catch-all user vs. territory rules)
3. Execute the bulk assignment
4. Verify all marketing contacts have owners (after state)

## Before

### Create the Unowned Marketing Contacts List

1. Go to **Contacts > Lists > Create list**
2. Select **Active list**
3. Name: `CLEANUP: Unowned Marketing Contacts`
4. Add filters:
   - Marketing contact status > is any of > Marketing contact
   - AND Contact owner > is unknown
5. Save the list and note the count

### Script Approach

Run `uv run skills/assign-unowned-contacts/scripts/before.py`. The core query:

```python
resp = requests.post(f"{BASE}/crm/v3/objects/contacts/search", headers=HEADERS, json={
    "filterGroups": [{"filters": [
        {"propertyName": "hs_marketable_status", "operator": "EQ", "value": "true"},
        {"propertyName": "hubspot_owner_id", "operator": "NOT_HAS_PROPERTY"},
    ]}],
    "limit": 1,
})
print(f"Unowned marketing contacts: {resp.json()['total']}")
```

## Execute

### Assignment Strategy Decision

Choose one of these approaches (requires team lead approval):

**Option A: Catch-All User (Simplest)**
- Assign all unowned contacts to a single integration/service user
- Pro: Fast, ensures 100% coverage immediately
- Con: One "owner" accumulates a large number of contacts; not meaningful for routing
- Best when: You plan to implement proper routing later and just need coverage now

**Option B: Territory/Region Rules**
- Assign based on contact geography, industry, or company size
- Pro: More meaningful ownership, better for sales follow-up
- Con: Requires a defined routing matrix and more complex execution
- Best when: You have established sales territories

**Option C: Round-Robin**
- Distribute evenly across active sales reps
- Pro: Fair distribution, immediate accountability
- Con: May assign contacts to reps who do not cover that segment
- Best when: Small team, all reps handle all segments

### Bulk Assignment via UI

1. Open the unowned marketing contacts list
2. Click the checkbox in the table header to select all contacts on the page
3. Click **Select all X contacts** to select across all pages
4. Click **Edit** in the toolbar
5. In the property dropdown, select **Contact owner**
6. Search for and select the chosen owner
7. Click **Update**
8. Confirm the bulk edit
9. For large numbers (5,000+), HubSpot processes in batches. This may take several minutes.

### Bulk Assignment via API

For the catch-all strategy, this is fully scripted: set `HUBSPOT_TARGET_OWNER_ID` in `.env` (run `before.py` to see available owner IDs) and run `uv run skills/assign-unowned-contacts/scripts/execute.py`.

```python
# What execute.py does:
# 1. POST /crm/v3/objects/contacts/search — unowned marketing contacts (paginated)
# 2. Build batch payload: {"inputs": [{"id": ..., "properties": {"hubspot_owner_id": OWNER_ID}}]}
# 3. POST /crm/v3/objects/contacts/batch/update in batches of 100

# For territory-based routing (extend the script):
# 1. Search for unowned marketing contacts with country/state/industry properties
# 2. Map each contact to an owner via your territory matrix
# 3. Batch update with the appropriate owner per contact
```

**API notes:**
- Get owner IDs from the Owners API: `GET /crm/v3/owners?limit=100`
- To find a specific owner by email: iterate through owners and match on `email`
- Batch update accepts up to 100 records per call
- Rate limit: 100 requests per 10 seconds

## After

Wait 5-10 minutes for HubSpot to finish processing, then verify: `uv run skills/assign-unowned-contacts/scripts/after.py` (re-runs the before-state query and compares against the baseline; the count should be 0).

**Verification checklist:**

1. The unowned marketing contacts list shows 0 contacts
2. Re-run the before-state script — count should be 0
3. Spot-check 5-10 contacts that were previously unowned — confirm they show the assigned owner
4. Check owner-based dashboards/reports to confirm the previously invisible contacts now appear

## Rollback

- Owner assignment is fully reversible: the execute script's CSV audit trail records every contact it assigned. To undo, batch-update those contact IDs with the previous owner (empty for "no owner").
- Individual assignments can also be reverted from each contact's property history.

## Key Technical Learnings

- **This is a business decision, not just a technical one.** Always get approval from sales/marketing leadership on the assignment strategy before executing. Bulk-assigning contacts to the wrong people creates confusion and erodes trust.
- **A catch-all user is a temporary solution.** If you assign to a single integration user, plan a follow-up process to redistribute contacts to actual sales reps when proper routing is established.
- **Pair with lead owner cleanup.** Once proper routing is in place, revisit contacts under the catch-all user and reassign them to real owners.
- **HubSpot bulk edit limits.** For very large batches (10,000+), the UI bulk edit may time out. Use the API approach instead, which handles pagination and batching gracefully.
- **New contacts need routing too.** After this one-time cleanup, implement a workflow or lead rotation rule to automatically assign owners to new marketing contacts going forward.
