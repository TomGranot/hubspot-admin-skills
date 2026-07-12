---
name: fix-lifecycle-stages
description: "Ensure all contacts and companies have appropriate lifecycle stages. Backfills missing stages via API, fixes records stuck at disallowed stages, and creates prevention workflows to stop future gaps."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: data-enrichment
---

# Fix Lifecycle Stages

Ensure every contact and company has an appropriate lifecycle stage. This includes backfilling missing stages, correcting disallowed stage values, and creating prevention workflows that automatically assign stages to new records.

## Why This Matters

Records without a lifecycle stage are invisible in pipeline reports, excluded from stage-based workflows, and cannot be properly segmented. Even a small percentage of missing lifecycle stages corrupts funnel reporting and makes pipeline analytics unreliable. Lifecycle stage data is also a prerequisite for lead scoring models and lifecycle progression workflows.

## Prerequisites

- Phase 1 hygiene processes completed (invalid/deleted contacts removed first)
- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with contact and company read/write scopes
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- Access to Contacts and Companies with bulk edit permissions
- Access to Automation > Workflows
- Understanding of HubSpot's lifecycle stage progression rules (see Critical Concept below)

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/fix-lifecycle-stages/scripts/before.py` |
| Execute | [`scripts/execute.py`](./scripts/execute.py) | `uv run skills/fix-lifecycle-stages/scripts/execute.py` |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run skills/fix-lifecycle-stages/scripts/after.py` |

`before.py` audits missing and per-stage counts for contacts and companies. `execute.py` performs the clear-then-set fixes (review its configuration block for the disallowed-stage mapping before running). `after.py` verifies coverage.

## Critical Concept: Forward-Only Lifecycle Progression

**HubSpot has forward-only lifecycle progression by default.** The built-in order is:

Subscriber > Lead > MQL > SQL > Opportunity > Customer > Evangelist

To move a record from a later stage (e.g., "Other", "Evangelist") to an earlier one (e.g., "Lead"), you must:

1. **FIRST** clear the lifecycle stage (set to blank/empty)
2. **THEN** set the new value

A direct set to an earlier stage will be **silently rejected** — no error, no warning, the value simply does not change. This is the single most common gotcha when fixing lifecycle stages.

```python
url = f"{BASE}/crm/v3/objects/contacts/{contact_id}"

# WRONG — silently fails if current stage is "later" than target
requests.patch(url, headers=HEADERS,
               json={"properties": {"lifecyclestage": "lead"}})

# CORRECT — clear first, then set (two separate calls)
requests.patch(url, headers=HEADERS,
               json={"properties": {"lifecyclestage": ""}})
requests.patch(url, headers=HEADERS,
               json={"properties": {"lifecyclestage": "lead"}})
```

## Plan

1. Audit missing and disallowed lifecycle stages (before state)
2. Define which stages are "disallowed" for your business and map them to correct stages
3. Fix contacts with disallowed stages (clear + re-set)
4. Set missing stages to appropriate defaults based on associated company context
5. Create prevention workflows for contacts and companies
6. Verify 100% coverage (after state)

## Before

### Audit Script

Run `uv run skills/fix-lifecycle-stages/scripts/before.py`. The core queries it runs:

```python
def count(object_type, filters):
    resp = requests.post(f"{BASE}/crm/v3/objects/{object_type}/search",
                         headers=HEADERS,
                         json={"filterGroups": [{"filters": filters}], "limit": 1})
    resp.raise_for_status()
    return resp.json()["total"]

missing = count("contacts", [
    {"propertyName": "lifecyclestage", "operator": "NOT_HAS_PROPERTY"}])
print(f"Contacts missing lifecycle stage: {missing}")

stages = ["subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead",
          "opportunity", "customer", "evangelist", "other"]
for stage in stages:
    n = count("contacts", [
        {"propertyName": "lifecyclestage", "operator": "EQ", "value": stage}])
    if n:
        print(f"  {stage}: {n}")

print(f"Companies missing lifecycle stage: "
      f"{count('companies', [{'propertyName': 'lifecyclestage', 'operator': 'NOT_HAS_PROPERTY'}])}")
```

### Define Disallowed Stages

Decide which lifecycle stage values should not exist in your database. The table below shows **common examples** -- your disallowed stages and their correct mappings will depend on how your organization uses the CRM. Review your own stage distribution and decide what makes sense for your business:

| Example Disallowed Stage | Common Reason | Example Correct Stage |
|--------------------------|---------------|----------------------|
| (empty/blank) | Invisible to reports | Lead (default) |
| Subscriber | Often misapplied when not used for newsletter-only contacts | Lead |
| Other | Meaningless catch-all | Lead |
| Evangelist | Rarely used correctly in most organizations | Customer (if actual customer) or Lead |

**These are starting-point examples only.** Your mapping will differ based on your sales process, integrations, and how stages are currently used. Define your specific mapping before executing.

## Execute

### Step 1: Fix Contacts at Disallowed Stages

For contacts at "Subscriber", "Other", or "Evangelist" that should be moved to "Lead":

```python
# Pattern: Clear then set (required for backward movement)
DISALLOWED_TO_LEAD = ["subscriber", "other", "evangelist"]

for stage in DISALLOWED_TO_LEAD:
    # Search for contacts at this stage
    # Paginate through all results
    # For each batch:
    #   1. Clear lifecycle stage (set to "")
    #   2. Set lifecycle stage to "lead"
    # Use batch API for efficiency (100 per call)
    pass
```

**Important:** The clear-then-set must happen as two separate API calls. You cannot clear and set in one call.

### Step 2: Set Missing Contact Stages with Context

Do not set all missing contacts to "Lead" blindly. Check their associated company context:

1. **Contacts at Customer companies** -> set to "Customer"
2. **Contacts at Opportunity companies** -> set to "Opportunity"
3. **All remaining contacts** -> set to "Lead"

```python
# Pattern for context-aware assignment:
# 1. Search for contacts with no lifecycle stage
# 2. For each, get their primary associated company
# 3. Check the company's lifecycle stage
# 4. Set the contact's stage to match (or "lead" as default)
```

**Manual approach via lists:**
1. Create a list: Lifecycle stage is unknown AND Associated company lifecycle stage is Customer -> bulk edit to "Customer"
2. Create a list: Lifecycle stage is unknown AND Associated company lifecycle stage is Opportunity -> bulk edit to "Opportunity"
3. Remaining contacts in the "no lifecycle stage" list -> bulk edit to "Lead"

### Step 3: Fix Companies Without Lifecycle Stage

1. Check companies with associated deals:
   - Companies with closed-won deals -> set to "Customer"
   - Companies with open deals -> set to "Opportunity"
2. All remaining companies without a stage -> set to "Lead"

### Step 4: Fix Stuck Records

Some records may fail to update due to the forward-only progression rule. Run a "fix stuck" script:

```python
# Pattern: Find records that should be at a stage but are not
# For each:
#   1. Read current lifecycle stage
#   2. If current stage is "later" than target, clear first
#   3. Set the target stage
```

### Step 5: Create Prevention Workflows

**Contact prevention workflow:**

1. Go to **Automation > Workflows > Create workflow**
2. Select **Contact-based > Blank workflow**
3. Name: `AUTO-FIX: Set Default Lifecycle Stage (Lead)`
4. Enrollment trigger: Contact property > Lifecycle stage > **is unknown**
5. Enable re-enrollment
6. Action: Set contact property > Lifecycle stage > **Lead**
7. Activate and enroll existing contacts

**Company prevention workflow:**

1. Create another workflow: **Company-based > Blank workflow**
2. Name: `AUTO-FIX: Set Default Company Lifecycle Stage (Lead)`
3. Enrollment trigger: Company property > Lifecycle stage > **is unknown**
4. Enable re-enrollment
5. Action: Set company property > Lifecycle stage > **Lead**
6. Activate and enroll existing companies

**Optional: Disallowed stage correction workflows:**

If contacts keep getting set to disallowed stages (e.g., by imports or integrations):

1. Create a workflow: Trigger = Lifecycle stage changed to "Subscriber" (or other disallowed value)
2. Action 1: Clear lifecycle stage (set to blank)
3. Action 2: Set lifecycle stage to "Lead"

This prevents disallowed stages from recurring.

## After

Re-run the audit: `uv run skills/fix-lifecycle-stages/scripts/after.py`. Both missing-stage counts (contacts and companies) should be 0.

**Verification checklist:**

1. 0 contacts with missing lifecycle stage
2. 0 companies with missing lifecycle stage
3. 0 contacts at disallowed stages (Subscriber, Other, Evangelist, or whatever you defined)
4. Spot-check contacts from Customer sub-list -> their lifecycle stage is "Customer"
5. Spot-check contacts from Opportunity sub-list -> their lifecycle stage is "Opportunity"
6. Test the prevention workflow: create a test contact with no lifecycle stage, wait a few minutes, confirm it gets set to "Lead". Delete the test contact.
7. Funnel reports now show all records with no "unknown" bucket

## Rollback

- The execute script's CSV audit trail records every record it changed with the original stage value. To undo, batch-update those IDs back to their previous stage (remember: moving backward requires the same clear-then-set pattern).
- Turn off the prevention workflows to stop automatic stage assignment.

## Key Technical Learnings

- **Forward-only progression is the biggest gotcha.** Direct API updates to an "earlier" stage are silently rejected. You MUST clear first, then set. This applies to both API and workflow actions.
- **"Lead" is the safest default.** It is early in the progression and will not block forward movement from workflows or deal progression. "Subscriber" is NOT a good default unless you know the contacts subscribed to a newsletter.
- **Context-aware assignment matters.** Setting a contact at a Customer company to "Lead" instead of "Customer" degrades data quality. Take the time to check associated company context.
- **Prevention is more important than cleanup.** The prevention workflows ensure the problem never recurs. Without them, new records from imports, integrations, or manual entry will immediately re-create the gap.
- **Lifecycle stage and deals interact.** HubSpot can automatically advance lifecycle stage when deals are created or won. Your prevention workflows will not interfere because they only trigger when lifecycle stage is unknown.
- **Batch edit limitations.** The UI may time out on very large bulk edits. Process one page at a time, or use the API approach for large volumes.
- **The sub-list approach is important.** Do not skip context-aware assignment and set everyone to "Lead". Contacts associated with Customer or Opportunity companies deserve the correct stage.
