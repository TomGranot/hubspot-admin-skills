---
name: review-bounced-contacts
description: "Weekly manual review of contacts with 3+ bounce events. Decide whether to delete or attempt recovery for each flagged contact. Prevents over-suppression while removing truly bad data."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: ongoing-maintenance
---

# Review Bounced Contacts

A weekly manual review process for contacts flagged with 3+ bounces. The bounce monitoring workflow auto-suppresses these contacts, but a human should decide whether to permanently delete or attempt recovery.

## Prerequisites

- Bounce monitoring workflow active (run `/bounce-monitoring-workflow` first)
- `email_health_flag` custom property exists on contacts
- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) for scripted pre-filtering

## Step-by-Step Instructions

### Stage 1: Before

Use the CRM Search API to pull contacts where `email_health_flag` is set:

```python
import os, requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

resp = requests.post(f"{BASE}/crm/v3/objects/contacts/search", headers=HEADERS, json={
    "filterGroups": [{"filters": [
        {"propertyName": "email_health_flag", "operator": "EQ", "value": "true"},
    ]}],
    "properties": ["email", "firstname", "lastname", "company",
                   "hs_email_bounce", "hs_email_hard_bounce_reason_enum",
                   "lifecyclestage", "hubspot_owner_id"],
    "limit": 100,
})
resp.raise_for_status()
results = resp.json()["results"]
```

Export results to a CSV for review.

### Stage 2: Execute — Review Each Contact

For each flagged contact, check:

1. **Is the email domain active?** Run a quick MX record lookup or visit the domain.
2. **Is this a known customer or high-value contact?** Check lifecycle stage and deal history.
3. **What is the bounce reason?** Hard bounce (invalid mailbox) vs. soft bounce (mailbox full, temporary error).

**Decision matrix:**

| Domain active? | High value? | Bounce type | Action |
|---------------|-------------|-------------|--------|
| No | Any | Any | Delete |
| Yes | No | Hard | Delete |
| Yes | No | Soft | Keep suppressed, recheck next quarter |
| Yes | Yes | Hard | Attempt to find updated email |
| Yes | Yes | Soft | Keep suppressed, monitor |

### Stage 3: After — Apply Decisions and Log

1. **Delete** contacts marked for deletion via the HubSpot UI or API batch delete.
2. **Clear** the `email_health_flag` on all reviewed contacts.
3. Log the review results (deleted count, kept count, recovery attempts) for the quarterly report.

## Rollback

- Deleted contacts can be restored from HubSpot's recycling bin within 90 days.
- Contacts kept as suppressed can be restored to marketing status via a workflow or manual update in the UI.

## MCP Note

This weekly triage is exactly the interactive, judgment-heavy work HubSpot's MCP server is good at (see `/connect-hubspot-mcp`): ask Claude to pull each flagged contact's details, deal history, and bounce reason conversationally while you decide delete-vs-recover.

## Frequency

Run weekly, ideally Monday morning. Should take 5-15 minutes depending on volume. If volume exceeds 50 contacts per week, investigate the root cause (bad list source, form spam, etc.).
