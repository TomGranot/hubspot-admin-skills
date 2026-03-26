---
name: cleanup-forms
description: "Audit and remove unused, test, or deprecated forms from HubSpot. Identifies forms with zero submissions, forms not embedded on any page, and test forms left over from development."
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: ongoing-maintenance
---

# Cleanup Forms

Audit HubSpot forms to remove unused and test forms. Stale forms clutter the forms dashboard and can cause confusion when building workflows or reports.

## Prerequisites

- HubSpot API token in `.env`
- Python with `hubspot-api-client` installed via `uv`
- Note: The Forms API may return 403 on some plan tiers. If so, perform the audit manually in the HubSpot UI under Marketing > Forms.

## Step-by-Step Instructions

### Stage 1: Before — Inventory All Forms

Pull all forms via the API:

```python
from hubspot import HubSpot

api_client = HubSpot(access_token=os.getenv("HUBSPOT_API_TOKEN"))
forms = api_client.marketing.forms.forms_api.get_page(limit=100)
```

For each form, record: form ID, name, type, submission count, created date, last submission date.

### Stage 2: Execute — Identify Candidates for Deletion

Flag forms matching any of these criteria:

1. **Zero submissions** and created more than 30 days ago
2. **No recent submissions** (last submission 6+ months ago) and not embedded on an active page
3. **Test forms** (names containing "test", "temp", "draft", "copy of")
4. **Deprecated forms** replaced by newer versions

Before deleting, check:
- Is the form referenced in any workflow enrollment trigger?
- Is the form embedded on any live landing page or website page?
- Is the form used in any pop-up or slide-in CTA?

### Stage 3: After — Delete and Document

1. Delete confirmed unused forms via the API or UI.
2. Document what was deleted in a cleanup log.
3. If a form with submissions is deleted, the submission data is retained on the contact records — but the form definition is gone.

### Stage 4: Rollback

- Deleted forms cannot be restored in HubSpot.
- Before deleting a form with any submissions, export the form definition (field names, settings) so it can be recreated.
- Contact records retain their form submission history regardless of form deletion.

## Tips

- Establish a naming convention: `[TEAM] - Purpose - Version` (e.g., `[Marketing] - Webinar Registration - v2`).
- Prefix deprecated forms with "[DEPRECATED]" instead of deleting immediately — delete after one quarter of no usage.
