---
name: cleanup-workflows
description: "Audit and remove inactive, test, or deprecated workflows from HubSpot. Identifies workflows that have never enrolled contacts, workflows turned off for 90+ days, and test workflows."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: ongoing-maintenance
---

# Cleanup Workflows

Audit HubSpot workflows to remove dead weight. Unused workflows clutter the automation dashboard and make it harder to understand what is actually running.

## Prerequisites

- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with the `automation` scope
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- Note: The Automation API may return 403 on some plan tiers. If so, audit manually in HubSpot UI under Automation > Workflows.
- Strongly recommended: run `/workflows-as-code` first to export a JSON backup of every workflow — deleted workflows cannot be restored, but an export lets you recreate them via the API.

## Step-by-Step Instructions

### Stage 1: Plan

Confirm with the user before starting:

1. Archive-first policy: turn off, wait a week, then delete (recommended)?
2. Any workflows that must never be touched (compliance, integrations)?

### Stage 2: Before

Inventory all workflows via the v4 Automation API:

```python
import os, requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

flows, after = [], None
while True:
    params = {"limit": 100}
    if after:
        params["after"] = after
    resp = requests.get(f"{BASE}/automation/v4/flows", headers=HEADERS, params=params)
    resp.raise_for_status()
    data = resp.json()
    flows.extend(data.get("results", []))
    after = data.get("paging", {}).get("next", {}).get("after")
    if not after:
        break
```

For each workflow, record: flow ID, name, enabled status, type, created date, last updated date. Enrollment counts are visible in the UI (Automation > Workflows > Details).

### Stage 3: Execute

Flag workflows matching any of these criteria:

1. **Turned off** for 90+ days with no plans to reactivate
2. **Zero enrollments** ever (likely test or abandoned drafts)
3. **Test workflows** (names containing "test", "temp", "copy of", "draft")
4. **Superseded workflows** replaced by newer versions
5. **Error state** workflows that have been failing consistently

Before deleting, check:
- Does the workflow feed into another workflow (via enrollment trigger or go-to-workflow action)?
- Does the workflow set properties that other workflows depend on?
- Is there any documentation referencing this workflow?

Present the candidate list to the user and wait for explicit confirmation. Then, for confirmed candidates: turn each workflow off first (in the UI, or `PUT /automation/v4/flows/{flowId}` with `isEnabled: false` — the PUT requires the current `revisionId`), wait one week, then delete via `DELETE /automation/v4/flows/{flowId}` or the UI.

### Stage 4: After

1. Re-run the inventory and confirm the deleted workflows are gone.
2. Document deleted workflows in a cleanup log (name, purpose, reason for deletion).
3. Notify workflow owners.

## Rollback

- Deleted workflows cannot be restored in HubSpot.
- A `/workflows-as-code` export taken beforehand contains each workflow's full JSON definition — recreate a deleted workflow with `POST /automation/v4/flows` from its export.
- HubSpot retains workflow activity history on contact records even after the workflow is deleted.

## Tips

- Use folders in the workflows dashboard to organize by team, purpose, or status.
- Prefix draft/test workflows with "[TEST]" so they are easy to identify later.
- Review workflows quarterly as part of the database cleanup routine.
