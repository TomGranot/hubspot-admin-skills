---
name: cleanup-forms
description: "Audit and remove unused, test, or deprecated forms from HubSpot. Identifies forms with zero submissions, forms not embedded on any page, and test forms left over from development."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: ongoing-maintenance
---

# Cleanup Forms

Audit HubSpot forms to remove unused and test forms. Stale forms clutter the forms dashboard and can cause confusion when building workflows or reports.

## Prerequisites

- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with `forms` scope
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- Note: The Forms API may return 403 on some plan tiers. If so, perform the audit manually in the HubSpot UI under Marketing > Forms.

## Step-by-Step Instructions

### Stage 1: Plan

Confirm with the user before starting:

1. How aggressive to be: delete outright, or prefix with "[DEPRECATED]" first and delete next quarter?
2. Any forms that must never be touched (compliance, legal, active campaigns)?

### Stage 2: Before

Inventory all forms via the Marketing Forms API (v3):

```python
import os, requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

forms, after = [], None
while True:
    params = {"limit": 100}
    if after:
        params["after"] = after
    resp = requests.get(f"{BASE}/marketing/v3/forms", headers=HEADERS, params=params)
    resp.raise_for_status()
    data = resp.json()
    forms.extend(data.get("results", []))
    after = data.get("paging", {}).get("next", {}).get("after")
    if not after:
        break
```

For each form, record: form ID, name, type, submission count, created date, last submission date.

### Stage 3: Execute

Flag forms matching any of these criteria:

1. **Zero submissions** and created more than 30 days ago
2. **No recent submissions** (last submission 6+ months ago) and not embedded on an active page
3. **Test forms** (names containing "test", "temp", "draft", "copy of")
4. **Deprecated forms** replaced by newer versions

Before deleting, check:
- Is the form referenced in any workflow enrollment trigger?
- Is the form embedded on any live landing page or website page?
- Is the form used in any pop-up or slide-in CTA?

Present the candidate list to the user and wait for explicit confirmation, then delete confirmed unused forms via the API (`DELETE /marketing/v3/forms/{formId}`) or UI.

### Stage 4: After

1. Re-run the inventory and confirm the deleted forms are gone.
2. Document what was deleted in a cleanup log.
3. If a form with submissions is deleted, the submission data is retained on the contact records — but the form definition is gone.

## Rollback

- Deleted forms cannot be restored in HubSpot.
- Before deleting a form with any submissions, export the form definition (field names, settings) so it can be recreated.
- Contact records retain their form submission history regardless of form deletion.

## Tips

- Establish a naming convention: `[TEAM] - Purpose - Version` (e.g., `[Marketing] - Webinar Registration - v2`).
- Prefix deprecated forms with "[DEPRECATED]" instead of deleting immediately — delete after one quarter of no usage.
