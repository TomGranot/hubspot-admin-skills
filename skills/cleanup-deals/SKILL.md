---
name: cleanup-deals
description: "Standardize deal pipelines, remove test deals, and address deals with missing amounts or close dates. Coordinates with Salesforce sync if applicable."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: ongoing-maintenance
---

# Cleanup Deals

Standardize deal data to make pipeline reporting accurate. Test deals, missing amounts, and stale opportunities distort forecasts and pipeline metrics.

## Prerequisites

- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with `crm.objects.deals.read` and `crm.objects.deals.write` scopes
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- Knowledge of which deal pipelines are active and which are synced from Salesforce

## Important: Salesforce Sync Considerations

If deals are synced from Salesforce:
- Do NOT delete or modify synced deals without coordinating with the Salesforce admin.
- Changes in HubSpot may sync back to Salesforce and cause data loss.
- Identify synced deals by checking for the `hs_salesforceopportunityid` property.

## Step-by-Step Instructions

### Stage 1: Plan

Confirm with the user before starting:

1. Which pipelines are in scope, and which are Salesforce-synced (hands off without coordination)?
2. The staleness cutoff for closing abandoned deals (default: 90 days without activity).

### Stage 2: Before

Pull deal metrics via the CRM Search API:

```python
import os, requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

def deal_count(prop, operator):
    resp = requests.post(f"{BASE}/crm/v3/objects/deals/search", headers=HEADERS, json={
        "filterGroups": [{"filters": [{"propertyName": prop, "operator": operator}]}],
        "limit": 1,
    })
    resp.raise_for_status()
    return resp.json()["total"]

no_amount = deal_count("amount", "NOT_HAS_PROPERTY")
no_close = deal_count("closedate", "NOT_HAS_PROPERTY")
```

Record: total deals, deals per pipeline stage, deals missing amount, deals missing close date, stale deals (open with no activity in 60+ days).

### Stage 3: Execute

1. **Delete test deals** — search for deals with names containing "test", "demo", "sample", or with amount = $0 and no associated contacts.
2. **Address missing amounts** — export deals without `amount` and work with sales to fill in values or mark as lost.
3. **Close stale deals** — deals open with no activity in 90+ days should be reviewed with the deal owner. Set to "Closed Lost" if abandoned.
4. **Standardize pipeline stages** — ensure all pipelines have consistent stage names and probability percentages.
5. **Remove unused pipelines** — if a pipeline has zero active deals and is not in use, archive or delete it.

### Stage 4: After

1. Re-run the deal audit queries. Confirm:
   - Test deals removed
   - Missing amount count decreased
   - Stale deal count decreased
2. Check pipeline reports for accuracy.

## Rollback

- Deleted deals can be restored from HubSpot's recycling bin within 90 days.
- Stage changes and property updates can be reverted manually but there is no bulk undo.
- For Salesforce-synced deals, check the Salesforce recycle bin as well.

## Tips

- Establish a deal hygiene rule: deals without activity for 60 days get an automated reminder to the owner (build a simple workflow).
- Require `amount` and `closedate` as mandatory deal properties to prevent future gaps.
