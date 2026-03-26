---
name: cleanup-deals
description: "Standardize deal pipelines, remove test deals, and address deals with missing amounts or close dates. Coordinates with Salesforce sync if applicable."
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: ongoing-maintenance
---

# Cleanup Deals

Standardize deal data to make pipeline reporting accurate. Test deals, missing amounts, and stale opportunities distort forecasts and pipeline metrics.

## Prerequisites

- HubSpot API token in `.env`
- Python with `hubspot-api-client` installed via `uv`
- Knowledge of which deal pipelines are active and which are synced from Salesforce

## Important: Salesforce Sync Considerations

If deals are synced from Salesforce:
- Do NOT delete or modify synced deals without coordinating with the Salesforce admin.
- Changes in HubSpot may sync back to Salesforce and cause data loss.
- Identify synced deals by checking for the `hs_salesforceopportunityid` property.

## Step-by-Step Instructions

### Stage 1: Before — Audit Deal Data

Pull deal metrics via the API:

```python
from hubspot import HubSpot
from hubspot.crm.deals import PublicObjectSearchRequest

api_client = HubSpot(access_token=os.getenv("HUBSPOT_API_TOKEN"))

# Deals missing amount
no_amount = PublicObjectSearchRequest(
    filter_groups=[{
        "filters": [{
            "propertyName": "amount",
            "operator": "NOT_HAS_PROPERTY"
        }]
    }]
)

# Deals missing close date
no_close = PublicObjectSearchRequest(
    filter_groups=[{
        "filters": [{
            "propertyName": "closedate",
            "operator": "NOT_HAS_PROPERTY"
        }]
    }]
)
```

Record: total deals, deals per pipeline stage, deals missing amount, deals missing close date, stale deals (open with no activity in 60+ days).

### Stage 2: Execute — Clean Up

1. **Delete test deals** — search for deals with names containing "test", "demo", "sample", or with amount = $0 and no associated contacts.
2. **Address missing amounts** — export deals without `amount` and work with sales to fill in values or mark as lost.
3. **Close stale deals** — deals open with no activity in 90+ days should be reviewed with the deal owner. Set to "Closed Lost" if abandoned.
4. **Standardize pipeline stages** — ensure all pipelines have consistent stage names and probability percentages.
5. **Remove unused pipelines** — if a pipeline has zero active deals and is not in use, archive or delete it.

### Stage 3: After — Verify

1. Re-run the deal audit queries. Confirm:
   - Test deals removed
   - Missing amount count decreased
   - Stale deal count decreased
2. Check pipeline reports for accuracy.

### Stage 4: Rollback

- Deleted deals can be restored from HubSpot's recycling bin within 90 days.
- Stage changes and property updates can be reverted manually but there is no bulk undo.
- For Salesforce-synced deals, check the Salesforce recycle bin as well.

## Tips

- Establish a deal hygiene rule: deals without activity for 60 days get an automated reminder to the owner (build a simple workflow).
- Require `amount` and `closedate` as mandatory deal properties to prevent future gaps.
