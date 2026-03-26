---
name: cleanup-workflows
description: "Audit and remove inactive, test, or deprecated workflows from HubSpot. Identifies workflows that have never enrolled contacts, workflows turned off for 90+ days, and test workflows."
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: ongoing-maintenance
---

# Cleanup Workflows

Audit HubSpot workflows to remove dead weight. Unused workflows clutter the automation dashboard and make it harder to understand what is actually running.

## Prerequisites

- HubSpot API token in `.env`
- Python with `hubspot-api-client` installed via `uv`
- Note: The Workflows API may return 403 on some plan tiers. If so, audit manually in HubSpot UI under Automation > Workflows.

## Step-by-Step Instructions

### Stage 1: Before — Inventory All Workflows

Pull all workflows. The Automation API endpoint for workflows:

```python
import requests

headers = {"Authorization": f"Bearer {os.getenv('HUBSPOT_API_TOKEN')}"}
response = requests.get(
    "https://api.hubapi.com/automation/v4/flows",
    headers=headers,
    params={"limit": 100}
)
workflows = response.json()
```

For each workflow, record: ID, name, enabled status, type, enrollment count, created date, last updated date.

### Stage 2: Execute — Identify Candidates for Deletion

Flag workflows matching any of these criteria:

1. **Turned off** for 90+ days with no plans to reactivate
2. **Zero enrollments** ever (likely test or abandoned drafts)
3. **Test workflows** (names containing "test", "temp", "copy of", "draft")
4. **Superseded workflows** replaced by newer versions
5. **Error state** workflows that have been failing consistently

Before deleting, check:
- Does the workflow feed into another workflow (via enrollment trigger)?
- Does the workflow set properties that other workflows depend on?
- Is there any documentation referencing this workflow?

### Stage 3: After — Delete and Document

1. Turn off workflows first, wait one week, then delete if no issues arise.
2. Document deleted workflows in a cleanup log (name, purpose, reason for deletion).
3. Notify workflow owners before deletion.

### Stage 4: Rollback

- Deleted workflows cannot be restored.
- Before deleting, screenshot or document the workflow logic (triggers, actions, branches) so it can be recreated if needed.
- HubSpot retains workflow activity history on contact records even after the workflow is deleted.

## Tips

- Use folders in the workflows dashboard to organize by team, purpose, or status.
- Prefix draft/test workflows with "[TEST]" so they are easy to identify later.
- Review workflows quarterly as part of the database cleanup routine.
