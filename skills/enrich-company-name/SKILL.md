---
name: enrich-company-name
description: "Populate missing contact company name fields from associated company records using a HubSpot workflow with optional API backfill. Ensures contacts inherit their company name for segmentation, personalization, and ICP classification."
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: data-enrichment
---

# Enrich Contact Company Name from Associated Company

Populate missing contact-level company name fields by copying the value from the associated company record. Uses a HubSpot workflow for ongoing enrichment and optionally an API backfill script for immediate results.

## Why This Matters

Contacts missing a company name cannot be matched to ICP-classified companies, break email personalization tokens, and are invisible to company-based segmentation. In a typical neglected CRM, 40-60% of contacts may be missing this field even though the vast majority have a company association.

## Prerequisites

- HubSpot Marketing Hub Professional or Sales Hub Professional (for Workflows)
- Phase 1 hygiene processes completed (invalid/deleted contacts removed first)
- **HubSpot auto-association enabled:** Settings > Objects > Companies > "Create and associate companies with contacts" toggle must be ON. This lets HubSpot automatically create company records from email domains and associate them.

## Plan

1. Enable auto-association if not already on
2. Audit how many contacts are missing company name (before state)
3. Build a workflow that copies company name from the associated company record
4. Optionally run an API backfill script for immediate results
5. Verify enrichment results (after state)

## Before State

Run a before-state audit to capture the baseline.

**Script approach (recommended):**

```python
import os
from hubspot import HubSpot
from dotenv import load_dotenv

load_dotenv()
api_client = HubSpot(access_token=os.getenv("HUBSPOT_API_TOKEN"))

# Count contacts missing company name
result = api_client.crm.contacts.search_api.do_search(
    public_object_search_request={
        "filterGroups": [{
            "filters": [{
                "propertyName": "company",
                "operator": "NOT_HAS_PROPERTY"
            }]
        }],
        "limit": 0
    }
)
print(f"Contacts missing company name: {result.total}")
```

**Manual approach:** Go to Contacts > filter by Company name > is unknown. Record the count.

Save the count. This is your baseline for measuring success.

## Execute

### Method 1: HubSpot Workflow (Recommended — Handles Backlog + Future)

1. Go to **Automation > Workflows > Create workflow**
2. Select **Contact-based > Blank workflow**
3. Name: `AUTO-ENRICH: Copy Company Name from Association`

**Enrollment trigger:**
- Contact property > Company name > **is unknown**

**Re-enrollment:**
- Enable re-enrollment when **associated company** changes. This is the safety net: if an association forms after the workflow already ran, the contact gets re-enrolled.

**Action 1: Delay 10 minutes**
- This delay is critical. When a new contact enters HubSpot, the auto-association engine needs time to parse the email domain, find or create a matching company, and create the association. Without this delay, the workflow checks for an association before one exists.

**Action 2: If/then branch**
- Condition: Associated company > Company name (or Name) > **is known**
- **YES branch:** Add a **Copy property** action:
  - Copy FROM: Company > Name
  - Copy TO: Contact > Company name
- **NO branch:** Leave empty (contact exits). These are typically contacts with personal email addresses (gmail, yahoo, etc.) where no company can be determined.

**Activate:**
- Click Review > Turn on
- When prompted, select **Yes, enroll existing contacts**. This enrolls the entire backlog.

### Method 2: API Backfill Script (Optional — Immediate Results)

Use this if you need the data populated immediately rather than waiting for workflow processing.

```python
# Pattern: Fetch contacts missing company name,
# look up their associated company, copy the name
from hubspot import HubSpot

api_client = HubSpot(access_token=os.getenv("HUBSPOT_API_TOKEN"))

# 1. Search for contacts missing company name
# 2. For each, get associations to companies
# 3. Fetch the primary company's name
# 4. Batch update the contact's company property
```

**Key API notes:**
- Use the Search API to find contacts where `company` NOT_HAS_PROPERTY
- Search API caps at 10,000 results. Segment by `createdate` ranges if needed.
- Use Associations API v4 to get contact-to-company associations
- Batch update contacts using `crm.contacts.batch_api.update`
- Respect rate limits: 100 requests per 10 seconds

### Why Do Both?

- The **workflow** handles both backlog (enrolled on activation) AND future contacts automatically. It is the long-term solution.
- The **API backfill** provides immediate results if you cannot wait for workflow processing (which may take hours for large databases).
- If you only do the workflow, that is perfectly fine. It will process the backlog since existing contacts meeting the trigger criteria get enrolled on activation.

## After State

Wait 1-2 hours after activating the workflow (longer for very large databases), then verify.

**Script approach:**

```python
# Same search as before-state script
result = api_client.crm.contacts.search_api.do_search(
    public_object_search_request={
        "filterGroups": [{
            "filters": [{
                "propertyName": "company",
                "operator": "NOT_HAS_PROPERTY"
            }]
        }],
        "limit": 0
    }
)
print(f"Contacts still missing company name: {result.total}")
```

**Verification checklist:**

1. The "missing company name" count should have dropped dramatically (typically from 40-60% to under 10%)
2. Remaining contacts without company names should primarily be those with personal email addresses (gmail.com, yahoo.com, etc.)
3. Spot-check 10-20 contacts to confirm the company name matches their associated company record
4. Check workflow history for errors:
   - Property type mismatch (copying to wrong field type)
   - Multiple associated companies (HubSpot uses the primary company)
5. Verify the workflow continues processing new contacts by checking for recent enrollments

## Key Technical Learnings

- **The 10-minute delay is a balance.** Auto-association typically completes in a few minutes, but 10 minutes provides a comfortable buffer. If many contacts go down the NO branch and later get associations, increase to 15-20 minutes.
- **Re-enrollment is the safety net.** Even if the delay is not long enough, re-enrollment on "associated company changes" catches late associations. The delay handles the common case; re-enrollment handles edge cases.
- **Primary company wins.** If a contact is associated with multiple companies, HubSpot copies from the primary associated company. Verify primary associations are correct for key contacts.
- **This workflow does NOT overwrite existing values.** The enrollment trigger requires "Company name is unknown", so contacts with an existing company name are never touched.
- **Property type matters.** Contact "Company name" is a single-line text field by default. If someone changed it to a dropdown, the copy action may fail. Check in Settings > Properties before running.
- **Personal email domains exit on the NO branch.** Contacts with gmail.com, yahoo.com, hotmail.com, outlook.com, etc. will not get enriched. This is expected. They need manual enrichment or a third-party tool (ZoomInfo, Clearbit, Apollo) to determine their company.
- **Company name is a prerequisite for ICP Tier classification.** Run this enrichment before creating ICP Tier workflows.
- **Schedule the "after" verification script.** Workflow processing for large databases takes time. Do not check results immediately — schedule the verification for 2-4 hours after activation.
