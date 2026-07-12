---
name: cleanup-properties
description: "Archive or delete unused custom properties across all HubSpot object types (contacts, companies, deals). Identifies Salesforce sync properties, test/temp properties, and obsolete form fields."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: ongoing-maintenance
---

# Cleanup Properties

Remove or archive unused custom properties. Property bloat slows down forms, confuses users, and makes data mapping harder.

## Prerequisites

- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with `crm.schemas.*.read` and `crm.schemas.*.write` scopes
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)

## Step-by-Step Instructions

### Stage 1: Plan

Confirm with the user before starting:

1. Archive-first policy (recommended) or direct deletion for clearly dead test properties?
2. Is a Salesforce (or other CRM) sync active? If yes, get the sync property mapping before touching anything.

### Stage 2: Before

Inventory custom properties for each object type via the Properties API (v3):

```python
import os, requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

for obj_type in ["contacts", "companies", "deals"]:
    resp = requests.get(f"{BASE}/crm/v3/properties/{obj_type}", headers=HEADERS)
    resp.raise_for_status()
    custom_props = [p for p in resp.json()["results"] if not p.get("hubspotDefined")]
```

For each custom property, record: name, label, object type, type, group, number of records with a value (requires search queries), whether it is used in any form/workflow/list.

### Stage 3: Execute

**Safe to delete:**
- Properties with zero populated records and not used in any form, workflow, or list
- Properties with names containing "test", "temp", "old_", "copy_of"
- Properties created by deactivated integrations

**Handle with care:**
- **Salesforce sync properties** (`hs_salesforce_*` prefix or mapped in sync settings) — do not delete without coordinating with the Salesforce admin
- **Form fields** — check if the property is used on any active form before deleting
- **Workflow dependencies** — check if any workflow reads or sets this property
- **Calculated properties** — check if other calculated properties reference this one

**Archive instead of delete** when:
- The property has historical data that might be needed for reporting
- You are unsure whether anything depends on it

Archive candidates via `DELETE /crm/v3/properties/{objectType}/{propertyName}` (this archives — the property moves to the archived state) after presenting the list to the user and getting explicit confirmation.

### Stage 4: After

1. Archive properties first (HubSpot supports property archiving).
2. Wait 30 days, then delete archived properties that caused no issues.
3. Document all changes in a cleanup log.

## Rollback

- Archived properties can be unarchived at any time.
- Deleted properties cannot be restored. The property definition and all associated data are permanently lost.
- Always archive before deleting to provide a safety window.

## Tips

- Run this quarterly as part of the database cleanup routine.
- Establish a property naming convention going forward (e.g., `team_purpose_detail`).
- Limit who can create custom properties to prevent sprawl.
- HubSpot has a property limit per object type — cleanup prevents hitting it.
