---
name: cleanup-lead-owners
description: "Remove non-employee users from HubSpot and reassign their orphaned contacts, companies, and deals. Pairs with the assign-unowned-contacts skill for comprehensive ownership cleanup."
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: ongoing-maintenance
---

# Cleanup Lead Owners

Remove departed employees from HubSpot and reassign their CRM records. Orphaned records with no active owner fall through the cracks.

## Prerequisites

- HubSpot API token in `.env`
- Python with `hubspot-api-client` installed via `uv`
- A list of current employees (to compare against HubSpot users)
- A default owner or round-robin assignment rule for orphaned records

## Step-by-Step Instructions

### Stage 1: Before — Identify Non-Employee Owners

```python
from hubspot import HubSpot

api_client = HubSpot(access_token=os.getenv("HUBSPOT_API_TOKEN"))

# Get all owners including deactivated
active_owners = api_client.crm.owners.owners_api.get_page(limit=100)
deactivated_owners = api_client.crm.owners.owners_api.get_page(
    limit=100, archived=True
)
```

Cross-reference with your current employee list. Flag:
- Deactivated HubSpot users who still own records
- Active HubSpot users who are no longer employees
- Contractors or vendors who should not own records

For each flagged owner, count how many contacts, companies, and deals they own.

### Stage 2: Execute — Reassign and Deactivate

1. **Reassign records** owned by non-employees:
   - Use the batch update API to reassign contacts to the appropriate active owner
   - Apply round-robin or territory-based rules if no specific owner is obvious
   - Reassign companies and deals associated with the same contacts

2. **Deactivate users** who are no longer employees (requires Super Admin in HubSpot Settings > Users & Teams).

3. **Run `/assign-unowned-contacts`** after reassignment to catch any records that ended up without an owner.

### Stage 3: After — Verify

1. Search for contacts where `hubspot_owner_id` matches any deactivated owner ID — count should be zero.
2. Confirm all reassigned contacts have an active owner.
3. Check that no workflows broke due to owner changes (some workflows may filter by specific owners).

### Stage 4: Rollback

- Owner reassignments can be reversed by batch-updating the `hubspot_owner_id` back to the original value.
- Keep a log of original owner assignments before making changes.
- Deactivated users can be reactivated in HubSpot Settings if needed.

## Tips

- Run this whenever an employee leaves the company — do not wait for quarterly cleanup.
- Set up an offboarding checklist that includes HubSpot record reassignment.
- Pairs with `/assign-unowned-contacts` for comprehensive ownership hygiene.
