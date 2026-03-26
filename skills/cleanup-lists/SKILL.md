---
name: cleanup-lists
description: "Audit and remove unused, empty, or duplicate list definitions from HubSpot. Identifies lists with zero members, lists not used by any workflow or email, and overlapping list criteria."
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: ongoing-maintenance
---

# Cleanup Lists

Audit HubSpot lists to remove clutter. Unused lists slow down the UI, confuse team members, and can mask the lists that actually matter.

## Prerequisites

- HubSpot API token in `.env`
- Python with `hubspot-api-client` installed via `uv`
- Note: Lists API access may return 403 on some plan tiers. If so, perform the audit manually in the UI.

## Step-by-Step Instructions

### Stage 1: Before — Inventory All Lists

Pull all lists via the API:

```python
from hubspot import HubSpot

api_client = HubSpot(access_token=os.getenv("HUBSPOT_API_TOKEN"))

lists = []
offset = 0
while True:
    response = api_client.crm.lists.lists_api.get_page(offset=offset, limit=100)
    lists.extend(response.results)
    if not response.paging or not response.paging.next:
        break
    offset = response.paging.next.after
```

For each list, record: list ID, name, type (active/static), member count, created date, last updated date.

Export to CSV for review.

### Stage 2: Execute — Identify Candidates for Deletion

Flag lists matching any of these criteria:

1. **Zero members** and created more than 30 days ago
2. **Not referenced** by any workflow, email, or ad audience
3. **Duplicate names** or nearly identical filter criteria
4. **Test/temp lists** (names containing "test", "temp", "copy of", "old")
5. **Static lists** that have not been updated in 6+ months

Cross-reference with workflows and email campaigns before deleting — a list with zero members might still be used as an enrollment trigger.

### Stage 3: After — Delete and Document

1. Delete confirmed unused lists via the API or UI.
2. Document what was deleted (list name, ID, reason) in a cleanup log.
3. Inform team members if any lists they created were removed.

### Stage 4: Rollback

- HubSpot does not have a list recycle bin. Deleted lists cannot be restored.
- Before deleting, export the list definition (filters/criteria) so it can be recreated if needed.
- Static lists: export member IDs before deletion if the membership data matters.

## Tips

- Run this quarterly as part of the database cleanup routine.
- Establish a naming convention going forward (e.g., prefix with team name or purpose).
- Archive lists by prefixing with "[ARCHIVE]" instead of deleting if you are unsure.
