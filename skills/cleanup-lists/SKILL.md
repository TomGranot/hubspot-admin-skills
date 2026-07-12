---
name: cleanup-lists
description: "Audit and remove unused, empty, or duplicate list definitions from HubSpot. Identifies lists with zero members, lists not used by any workflow or email, and overlapping list criteria."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: ongoing-maintenance
---

# Cleanup Lists

Audit HubSpot lists to remove clutter. Unused lists slow down the UI, confuse team members, and can mask the lists that actually matter.

## Prerequisites

- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with `crm.lists.read` (and `crm.lists.write` for deletion)
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- Note: Lists API access may return 403 on some plan tiers. If so, perform the audit manually in the UI.

## Step-by-Step Instructions

### Stage 1: Plan

Confirm with the user before starting:

1. Delete outright, or prefix with "[ARCHIVE]" first and delete next quarter?
2. Any lists that must never be touched (suppression lists, compliance segments, active campaign audiences)?

### Stage 2: Before

Inventory all lists via the Lists API (v3):

```python
import os, requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

lists, offset = [], 0
while True:
    resp = requests.post(f"{BASE}/crm/v3/lists/search", headers=HEADERS,
                         json={"offset": offset, "count": 100})
    resp.raise_for_status()
    data = resp.json()
    lists.extend(data.get("lists", []))
    if not data.get("hasMore"):
        break
    offset = data.get("offset", offset + 100)
```

For each list, record: list ID, name, processing type (DYNAMIC/MANUAL), member count (`additionalProperties`), created date, last updated date.

Export to CSV for review.

### Stage 3: Execute

Flag lists matching any of these criteria:

1. **Zero members** and created more than 30 days ago
2. **Not referenced** by any workflow, email, or ad audience
3. **Duplicate names** or nearly identical filter criteria
4. **Test/temp lists** (names containing "test", "temp", "copy of", "old")
5. **Static lists** that have not been updated in 6+ months

Cross-reference with workflows and email campaigns before deleting — a list with zero members might still be used as an enrollment trigger.

Present the candidate list to the user and wait for explicit confirmation, then delete via `DELETE /crm/v3/lists/{listId}` or the UI.

### Stage 4: After

1. Re-run the inventory and confirm the deleted lists are gone.
2. Document what was deleted (list name, ID, reason) in a cleanup log.
3. Inform team members if any lists they created were removed.

## Rollback

- HubSpot does not have a list recycle bin. Deleted lists cannot be restored.
- Before deleting, export the list definition (filters/criteria) so it can be recreated if needed.
- Static lists: export member IDs before deletion if the membership data matters.

## Tips

- Run this quarterly as part of the database cleanup routine.
- Establish a naming convention going forward (e.g., prefix with team name or purpose).
- Archive lists by prefixing with "[ARCHIVE]" instead of deleting if you are unsure.
