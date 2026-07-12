---
name: enrich-industry
description: "Backfill contact-level industry from associated company records using a HubSpot workflow. Enables industry-based segmentation for targeted campaigns aligned with ICP verticals."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: data-enrichment
---

# Enrich Contact Industry from Associated Company

Copy industry data from company records to their associated contacts. In a typical B2B CRM, company records have industry populated at high rates (80-90%) while contact records have almost none. This workflow bridges that gap automatically.

## Why This Matters

Without industry on contact records, you cannot segment email campaigns by vertical. For B2B companies targeting specific industries, this makes the difference between spray-and-pray email blasts and targeted, relevant messaging. Industry data on contacts also feeds ICP tier classification and lead scoring models.

## Prerequisites

- HubSpot Marketing Hub Professional or Sales Hub Professional (for Workflows)
- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) for the scripted stages
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- Company name enrichment (enrich-company-name skill) should be completed first, as it may trigger new company associations
- Access to Settings > Properties to verify/create the contact Industry property

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/enrich-industry/scripts/before.py` |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run skills/enrich-industry/scripts/after.py` |

There is no execute script: the enrichment itself runs as a HubSpot workflow (see Execute below).

## Plan

1. Verify the contact Industry property exists and is compatible with the company Industry property
2. Audit how many contacts can be enriched (before state)
3. Build a workflow that copies industry from the associated company
4. Verify enrichment results (after state)

## Before

### Check Property Compatibility

This is the most important pre-step. Contacts may have TWO industry properties: `industry` and `industry_name`. You must verify which one HubSpot uses for lists and reports.

1. Go to **Settings > Properties > Contact properties**
2. Search for "Industry"
3. Note ALL industry-related properties on the contact object
4. Check which property is used in existing lists, reports, and workflows
5. The target property must be compatible with the company Industry property:
   - If both are **dropdown select**: option values must match exactly (same spelling, same case)
   - If the contact property is **single-line text**: it will accept any value (safest option)
   - If unsure, use single-line text to avoid copy failures

**If no contact Industry property exists**, create one:
- Object: Contact
- Group: Contact information
- Label: Industry
- Field type: Dropdown select (copy all values from the company Industry property) OR Single-line text (accepts any value)

### Audit Enrichment Opportunity

Run `uv run skills/enrich-industry/scripts/before.py`. The core query:

```python
resp = requests.post(f"{BASE}/crm/v3/objects/contacts/search", headers=HEADERS, json={
    "filterGroups": [{"filters": [
        {"propertyName": "industry", "operator": "NOT_HAS_PROPERTY"},
    ]}],
    "limit": 1,
})
print(f"Contacts missing industry: {resp.json()['total']}")
```

Also create a HubSpot list to estimate enrichable contacts:
- Filter 1: Contact Industry > is unknown
- Filter 2: AND Associated company > Industry > is known
- This count tells you how many contacts will actually be enriched

## Execute

### Create the Enrichment Workflow

This workflow is nearly identical to the company name enrichment workflow. If you already built that one, clone it and swap the property references.

1. Go to **Automation > Workflows > Create workflow**
2. Select **Contact-based > Blank workflow**
3. Name: `AUTO-ENRICH: Copy Industry from Company`

**Enrollment trigger:**
- Contact property > Industry > **is unknown**
- AND Associated company > Industry > **is known**

**Re-enrollment:**
- Enable re-enrollment on the same criteria. This ensures contacts that later get associated with a company are also enriched.

**Action: Copy property**
- Copy FROM: Company > Industry
- Copy TO: Contact > Industry

**Activate:**
- Click Review > Turn on
- Select **Yes, enroll existing contacts**

**Note:** Unlike the company name workflow, no delay is needed here. If the contact already has an associated company with industry data (checked by the enrollment trigger), the copy can happen immediately.

## After

Wait 1-2 hours for the workflow to process, then verify: `uv run skills/enrich-industry/scripts/after.py` (re-runs the before-state query and compares against the baseline).

**Verification checklist:**

1. Contact industry count should jump from near-zero to tens of thousands
2. The enrichment list (missing industry + has company association) should be near 0
3. Spot-check 20+ contacts for accuracy:
   - Open the contact record
   - Verify the Industry field shows a value
   - Click the associated company and confirm the industry matches
4. Check that the industry distribution on contacts roughly mirrors the company industry distribution
5. Check workflow history for failures — most common is property value mismatch (company has a value that does not match a dropdown option on the contact)

## Rollback

- Turn off the workflow to stop further enrichment.
- The workflow only fills empty fields. If wrong values were copied (e.g., mismatched dropdown options), filter contacts by the workflow's enrollment history and clear the contact `industry` property, or restore individual values from property history.

## External Providers

This skill only moves industry data the portal already has (company → contact). When the *company* itself has no industry value, that gap needs external data — see `/waterfall-enrich-contacts` for the provider-agnostic enrichment path, or HubSpot's Breeze Intelligence add-on for in-platform enrichment.

## Key Technical Learnings

- **Two industry properties can exist.** Some HubSpot portals have both `industry` and `industry_name` on contacts. Verify which one is authoritative before building the workflow. Writing to the wrong one means your lists and reports will not see the data.
- **Dropdown value matching is case-sensitive and exact.** If the company Industry has "Healthcare" and the contact Industry dropdown has "healthcare" (lowercase), the copy will fail. Ensure values match exactly.
- **Consider consolidating similar industries.** Many CRMs have overlapping values like "Healthcare" and "Hospital & Health Care". For segmentation, consider creating a separate "Industry Group" property that maps similar values into broader categories. This is optional but improves list usability.
- **This does not overwrite existing values.** The enrollment trigger requires "Industry is unknown", so contacts that already have industry data are not affected.
- **If using a text field instead of dropdown:** Enrichment works, but you lose the ability to filter by exact dropdown values in lists. You can convert to a dropdown later but will need to clean up inconsistent text values first.
- **Run this after company name enrichment.** Company name enrichment may trigger new company associations, which increases the number of contacts eligible for industry enrichment.
- **Clone the company name workflow.** The structure is nearly identical. Clone it in HubSpot and swap the property references to save time.
