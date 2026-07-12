---
name: standardize-geo-values
description: "Convert inconsistent country and state/region formats to standardized values across contacts and companies. Ensures geographic segmentation works reliably."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: data-enrichment
---

# Standardize Country and State/Region Values

Convert inconsistent geographic formats (e.g., "US", "USA", "U.S." vs "United States"; "NY" vs "New York") to a single standard format across all contact and company records.

## Why This Matters

Inconsistent geo values break geographic segmentation. A list filtering for "United States" will miss contacts labeled "US" or "USA". For B2B companies running region-specific campaigns or reporting by geography, this means inaccurate audience sizes and missed contacts.

## Prerequisites

- Phase 1 hygiene processes completed (invalid/deleted contacts removed first)
- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with contact and company read/write scopes
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- Access to Contacts and Companies views with bulk edit permissions
- **Key constraint:** If your CRM integrates with another system (e.g., Salesforce, marketing automation), agree on the standard format (full names vs. ISO codes) with that system's admin BEFORE standardizing. Mismatched formats between synced systems will cause ongoing data conflicts.
- Decision on standard format. This skill recommends:
  - Countries: Full names (e.g., "United States", "United Kingdom")
  - States (contact level): Full names (e.g., "New York", "California")
  - This matches HubSpot's default form behavior

## Interview: Gather Requirements

Before executing, collect the following information from the user:

**Q1: What format do you prefer for country values -- full names (United States) or ISO codes (US)?**
- Examples: Full names ("United States", "United Kingdom"), ISO 2-letter codes ("US", "GB"), ISO 3-letter codes ("USA", "GBR")
- Default: Full names (e.g., "United States", "United Kingdom") -- this matches HubSpot's default form behavior

**Q2: Do you have a Salesforce or other CRM integration that requires a specific format?**
- Examples: "Yes, Salesforce uses ISO 2-letter codes", "Yes, our ERP uses full country names", "No integrations to worry about"
- Default: No integration constraints -- use HubSpot's default full-name format

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/standardize-geo-values/scripts/before.py` |
| Execute | [`scripts/execute.py`](./scripts/execute.py) | `uv run skills/standardize-geo-values/scripts/execute.py` |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run skills/standardize-geo-values/scripts/after.py` |

`before.py` counts contacts and companies per variant value. `execute.py` applies the variant-to-standard mapping via batch update (review and extend its `COUNTRY_MAPPING`/`STATE_MAPPING` tables first). `after.py` verifies all variants return zero.

## Plan

1. Audit all non-standard country and state values (before state)
2. Build a mapping table of variants to standard values
3. Batch update via API script or manual bulk edit in HubSpot UI
4. Prevent future inconsistencies by configuring property types and forms
5. Verify all values are standardized (after state)

## Before

### API Audit Script

Run `uv run skills/standardize-geo-values/scripts/before.py`. The core query pattern:

```python
variants = ["US", "USA", "U.S.", "U.S.A.", "America"]
for object_type in ["contacts", "companies"]:
    for variant in variants:
        resp = requests.post(f"{BASE}/crm/v3/objects/{object_type}/search",
                             headers=HEADERS, json={
            "filterGroups": [{"filters": [
                {"propertyName": "country", "operator": "EQ", "value": variant},
            ]}],
            "limit": 1,
        })
        total = resp.json()["total"]
        if total:
            print(f"{object_type} with country = '{variant}': {total}")
```

### Manual Audit

1. Go to Contacts > filter by Country/Region > is any of > "US". Note count.
2. Repeat for "USA", "U.S.", and any other suspected variants.
3. Repeat at the company level.
4. For states: filter by State/Region > is any of > "NY", "CA", "TX" to check for abbreviation variants.

Record all variant counts as your baseline.

## Execute

### Method 1: API Batch Update (Recommended for Large Volumes)

This is scripted: `uv run skills/standardize-geo-values/scripts/execute.py`. The mapping tables it applies:

```python
COUNTRY_MAPPING = {
    "US": "United States",
    "USA": "United States",
    "U.S.": "United States",
    "U.S.A.": "United States",
    "America": "United States",
    "UK": "United Kingdom",
    "GB": "United Kingdom",
    "Great Britain": "United Kingdom",
    # Add other mappings as discovered in your audit
}

STATE_MAPPING = {
    "NY": "New York",
    "CA": "California",
    "TX": "Texas",
    "FL": "Florida",
    "IL": "Illinois",
    "PA": "Pennsylvania",
    "OH": "Ohio",
    "GA": "Georgia",
    "NC": "North Carolina",
    "NJ": "New Jersey",
    "VA": "Virginia",
    "WA": "Washington",
    "MA": "Massachusetts",
    "AZ": "Arizona",
    "CO": "Colorado",
    "MD": "Maryland",
    "MN": "Minnesota",
    "MO": "Missouri",
    "WI": "Wisconsin",
    "CT": "Connecticut",
    "OR": "Oregon",
    "SC": "South Carolina",
    "LA": "Louisiana",
    # Add all 50 US states + territories as needed
}

# For each mapping the script:
# 1. Searches for contacts with the variant value (POST /crm/v3/objects/contacts/search)
# 2. Collects all matching contact IDs (paginated via the `after` cursor)
# 3. Batch updates them (POST /crm/v3/objects/contacts/batch/update, 100 per call)
# 4. Repeats for companies (/crm/v3/objects/companies/...)
```

**API notes:**
- Search API caps at 10,000 results per query. Unlikely to hit this for geo variants, but segment if needed.
- Batch update accepts up to 100 records per call.
- Rate limit: 100 requests per 10 seconds.

### Method 2: Manual Bulk Edit in HubSpot UI

For each variant:

1. Go to **Contacts > Lists > Create list** (static)
2. Filter: Country/Region > is any of > [variant value]
3. Save list
4. Select all contacts in the list
5. Click **Edit** > Country/Region > type the standard value > Update
6. Repeat for each variant

For companies, do the same from the Companies view using filters and bulk edit.

### Prevent Future Inconsistencies

After standardizing existing data:

1. Go to **Settings > Properties > Contact properties**
2. Search for **Country/Region**
3. Verify it is a **Dropdown select** field (not free text). If it is free text, consider converting to dropdown with standard country names.
4. Repeat for **State/Region** (though state may need values for multiple countries, making a dropdown less practical)
5. Check all active **Forms** (Marketing > Forms):
   - Verify country and state fields are dropdown fields, not free text inputs
   - Verify dropdown values match your standardized format
6. Check any **import templates** used by the team to ensure they reference standard values

## After

Re-run the variant checks: `uv run skills/standardize-geo-values/scripts/after.py`. Every variant should return 0 for both contacts and companies.

**Verification checklist:**

1. All known variant values return 0 contacts and 0 companies
2. The standard value count should equal the sum of (previous standard count + all variant counts)
3. Spot-check 10 contacts that were in cleanup lists to verify values are now standardized
4. For states: filter by common abbreviations (NY, CA, TX) and confirm 0 results
5. Forms are configured to prevent future inconsistencies

## Rollback

- The execute script's CSV audit trail records every record it changed with the original value. To undo, batch-update those IDs back to their previous values.
- Individual values can also be reverted from each record's property history.

## Key Technical Learnings

- **Do not touch blank/empty values in this process.** Filling in missing country data is a separate enrichment task. This process only standardizes existing values that are non-empty but non-standard.
- **Coordinate with integrated systems first.** If HubSpot syncs with Salesforce or another CRM, mismatched formats cause sync conflicts. Agree on the standard format before changing anything.
- **Company-level state abbreviations may be acceptable.** HubSpot's default behavior for company State/Region often uses abbreviations. Decide whether to standardize company states or leave them as-is.
- **Root cause matters as much as cleanup.** The variants were likely created by imports, API integrations, or free-text form fields that bypassed dropdowns. Fixing the root cause (forms, import templates, integration mappings) is as important as fixing existing data.
- **Export before editing (optional safety measure).** Before bulk editing, export affected contacts/companies with their current values as a backup CSV.
- **Bulk edit limits vary by plan.** HubSpot may limit bulk edits to certain batch sizes (100-250 at a time). For large numbers, you may need to repeat the select-all-and-edit process multiple times, or use the API approach instead.
