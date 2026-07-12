---
name: cleanup-lead-owners
description: "Remove non-employee users from HubSpot and reassign their orphaned contacts, companies, and deals. Pairs with the assign-unowned-contacts skill for comprehensive ownership cleanup."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: ongoing-maintenance
---

# Cleanup Lead Owners

Remove departed employees from HubSpot and reassign their CRM records. Orphaned records with no active owner fall through the cracks.

## Prerequisites

- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with `crm.objects.owners.read` and contact/company/deal write scopes
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- A list of current employees (to compare against HubSpot users)
- A default owner or round-robin assignment rule for orphaned records

## Step-by-Step Instructions

### Stage 1: Plan

Confirm with the user before starting:

1. Who receives reassigned records — a single default owner, or territory/round-robin rules?
2. Which flagged users should be deactivated vs merely stripped of records?

### Stage 2: Before

Identify non-employee owners via the Owners API:

```python
import os, requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

active = requests.get(f"{BASE}/crm/v3/owners", headers=HEADERS,
                      params={"limit": 100, "archived": "false"}).json()["results"]
deactivated = requests.get(f"{BASE}/crm/v3/owners", headers=HEADERS,
                           params={"limit": 100, "archived": "true"}).json()["results"]
```

Cross-reference with your current employee list. Flag:
- Deactivated HubSpot users who still own records
- Active HubSpot users who are no longer employees
- Contractors or vendors who should not own records

For each flagged owner, count how many contacts, companies, and deals they own.

### Stage 3: Execute

1. **Reassign records** owned by non-employees:
   - Use the batch update API to reassign contacts to the appropriate active owner
   - Apply round-robin or territory-based rules if no specific owner is obvious
   - Reassign companies and deals associated with the same contacts

2. **Deactivate users** who are no longer employees (requires Super Admin in HubSpot Settings > Users & Teams).

3. **Run `/assign-unowned-contacts`** after reassignment to catch any records that ended up without an owner.

### Stage 4: After

1. Search for contacts where `hubspot_owner_id` matches any deactivated owner ID — count should be zero.
2. Confirm all reassigned contacts have an active owner.
3. Check that no workflows broke due to owner changes (some workflows may filter by specific owners).

## Rollback

- Owner reassignments can be reversed by batch-updating the `hubspot_owner_id` back to the original value.
- Keep a log of original owner assignments before making changes.
- Deactivated users can be reactivated in HubSpot Settings if needed.

## Tips

- Run this whenever an employee leaves the company — do not wait for quarterly cleanup.
- Set up an offboarding checklist that includes HubSpot record reassignment.
- Pairs with `/assign-unowned-contacts` for comprehensive ownership hygiene.
