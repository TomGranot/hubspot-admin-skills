---
name: create-segment-lists
description: "Create business segment lists in HubSpot for customers, partners, competitors, employees, ICP tiers, and industries. Enables segment-based targeting, suppression, and analytics."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: ongoing-maintenance
---

# Create Segment Lists

Build a library of segment lists that enable targeted marketing, accurate reporting, and proper suppression. These lists form the foundation of segment-based operations.

## Prerequisites

- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with `crm.lists.read` and `crm.lists.write` scopes
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- ICP tier property created (run `/create-icp-tiers` first)
- Lifecycle stages cleaned up (run `/fix-lifecycle-stages` first)

## Interview: Gather Requirements

Before executing, collect the following information from the user:

**Q1: What are your key customer segments?**
- Examples: Industry verticals (Manufacturing, Professional Services, Retail, Education, Logistics), company size tiers (Enterprise, Mid-Market, SMB), geographic regions (North America, EMEA, APAC)
- Default: Core business segments (Customers, Partners, Competitors, Internal) plus ICP tiers and engagement-based segments

**Q2: What engagement criteria define "active" for your business?**
- Examples: Email open or click in last 90 days, website visit in last 60 days, form submission in last 30 days, meeting booked in last 90 days
- Default: Any email engagement (open or click) within the last 90 days

## Recommended Segments

### Core Business Segments

| List Name | Type | Criteria |
|-----------|------|----------|
| All Customers | Active | Lifecycle stage = Customer |
| All Partners | Active | Contact type = Partner (or custom property) |
| Competitors | Static | Manually curated from known competitor domains |
| Internal Employees | Active | Email domain matches company domain |
| Suppressed Contacts | Active | Marketing status = non-marketing OR globally unsubscribed |

### ICP-Based Segments

| List Name | Type | Criteria |
|-----------|------|----------|
| ICP Tier 1 | Active | ICP tier property = Tier 1 |
| ICP Tier 2 | Active | ICP tier property = Tier 2 |
| ICP Tier 3 | Active | ICP tier property = Tier 3 |
| Non-ICP | Active | ICP tier property = Non-ICP or unknown |

### Industry Segments

| List Name | Type | Criteria |
|-----------|------|----------|
| [Industry Name] | Active | Industry = [value] |
| (Create one per target industry) | | |

### Engagement Segments

| List Name | Type | Criteria |
|-----------|------|----------|
| Highly Engaged (90 days) | Active | Email open or click in last 90 days |
| Disengaged (6+ months) | Active | No email engagement in 180+ days |
| Never Engaged | Active | No email opens ever AND created 30+ days ago |

## Step-by-Step Instructions

### Stage 1: Plan

1. Run the requirements interview above and decide which segments are relevant to the business.
2. Check for existing lists that overlap — merge or rename rather than creating duplicates.

### Stage 2: Before

1. Confirm the properties these lists depend on are populated (ICP tier, lifecycle stage, industry).
2. Inventory existing lists (`POST /crm/v3/lists/search`) and record the baseline count.

### Stage 3: Execute — Create Lists

Use the Lists API (v3) to create active (smart) lists:

```python
import os, requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
BASE = "https://api.hubapi.com"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Example: Create "All Customers" list
resp = requests.post(f"{BASE}/crm/v3/lists", headers=HEADERS, json={
    "name": "All Customers",
    "objectTypeId": "0-1",  # contacts
    "processingType": "DYNAMIC",
    "filterBranch": {
        "filterBranchType": "OR",
        "filterBranches": [{
            "filterBranchType": "AND",
            "filterBranches": [],
            "filters": [{
                "filterType": "PROPERTY",
                "property": "lifecyclestage",
                "operation": {
                    "operationType": "ENUMERATION",
                    "operator": "IS_ANY_OF",
                    "values": ["customer"],
                },
            }],
        }],
        "filters": [],
    },
})
resp.raise_for_status()
```

Create each list, verify member count, and document the list ID.

For static lists (Competitors), create the list and manually add contacts or import from a CSV.

### Stage 4: After

1. Check member counts for each list — do they match expectations?
2. Verify no contacts appear in mutually exclusive lists (e.g., both Customer and Competitor).
3. Confirm lists are visible to the appropriate teams.

## Rollback

- Lists can be deleted via the API or UI.
- Deleting a list does not affect the contacts in it — only the list definition is removed.
- Check if any workflows or emails reference the list before deleting.

## Tips

- Use a consistent naming convention: `[Category] - Segment Name` (e.g., `[ICP] - Tier 1`, `[Industry] - Manufacturing`).
- Review segment membership quarterly — segments should grow or shrink in expected ways.
- Use these lists as building blocks for email sends, ad audiences, and workflow enrollment triggers.
