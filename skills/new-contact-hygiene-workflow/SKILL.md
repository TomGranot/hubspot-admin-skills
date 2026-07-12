---
name: new-contact-hygiene-workflow
description: "Build a HubSpot workflow that auto-enriches and stages new contacts upon creation. Sets lifecycle stage via the v4 Automation API, copies company name and industry from the associated company (UI step), and branches on completeness."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: automation-workflows
---

# New Contact Hygiene Workflow

Build a workflow that automatically enriches every new contact at creation time. This ensures contacts enter the database with a lifecycle stage, company name, and industry before any human touches them.

## What Is and Isn't Scriptable

The v4 Automation API (stable) creates workflows programmatically, including "is unknown" enrollment conditions via `LIST_BASED` filter criteria. Two pieces of this particular design still belong in the UI:

1. **Copy from associated object** actions (copy company name/industry from the associated company) have no documented v4 action fields. Add them in the UI during review — or build the action once in the UI, `GET /automation/v4/flows/{flowId}`, and extend the script with the exact field shapes your portal returns.
2. **The notification branch** (alert admin when a contact still has no company after the delay) depends on portal-specific recipients.

So the split is: the script creates the default-lifecycle-stage workflow via API; the enrichment copy actions and the notification branch are added in the UI. If you already run `/enrich-company-name` and `/enrich-industry`, their dedicated workflows cover the copy actions and this skill's API-created workflow completes the intake picture.

## Prerequisites

- HubSpot Marketing Professional or Enterprise plan
- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with the `automation` scope (for the API path)
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- Workflow creation permissions in HubSpot
- Company association enrichment completed (run `/enrich-company-name` and `/enrich-industry` first for existing contacts)

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/new-contact-hygiene-workflow/scripts/before.py` |
| Execute | [`scripts/execute.py`](./scripts/execute.py) | `uv run skills/new-contact-hygiene-workflow/scripts/execute.py` |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run skills/new-contact-hygiene-workflow/scripts/after.py` |

`execute.py` creates one workflow — "HYGIENE: Default Lifecycle Stage for New Contacts" (enrollment: create date known AND lifecycle stage unknown; action: set stage to Lead; re-enrollment on) — **disabled, for review before enabling**. Extend it in the UI with the copy actions and notification branch per the design below.

## Building the Workflow: Two Options

**Option A (primary):** run the scripts, then extend the created workflow in the UI with the copy-from-associated-company actions, the delay, and the no-company notification branch (Stage 3, steps 3-6).

**Option B:** build the whole workflow manually in the UI (all of Stage 3).

**Alternatives:** HubSpot Breeze AI provides minimal value for this workflow — it creates event-based (OR) triggers, and cannot create "is unknown" conditions, copy-from-association actions, or re-enrollment rules. The Claude Chrome extension can drive the workflow builder UI directly and handles those cases. Both are secondary options.

## Workflow Design

```
TRIGGER: Contact create date is known
         (fires for every new contact)
           │
           ▼
    ┌─────────────────────────┐
    │ Set lifecycle stage      │
    │ = "Lead" (if empty)      │
    └────────────┬────────────┘
                 │
                 ▼
    ┌─────────────────────────┐
    │ Copy company name from   │
    │ associated company       │
    └────────────┬────────────┘
                 │
                 ▼
    ┌─────────────────────────┐
    │ Copy industry from       │
    │ associated company       │
    └────────────┬────────────┘
                 │
                 ▼
    ┌─────────────────────────┐
    │ Delay: short wait         │
    │ (3-10 min, rec: 5)      │
    └────────────┬────────────┘
                 │
                 ▼
    ┌─────────────────────────┐
    │ IF/THEN BRANCH:          │
    │ Company name is unknown? │
    ├──────────┬──────────────┘
    │ YES      │ NO
    │          │
    ▼          ▼
  Retry      Continue
  copy       (enriched)
  + notify
  admin
```

## Step-by-Step Build Instructions

### Stage 1: Plan

1. Confirm the default stage for new contacts (Lead, unless your funnel differs).
2. Decide who receives the "no company association" notification.

### Stage 2: Before

1. Confirm company enrichment processes have run for existing data.
2. Run `uv run skills/new-contact-hygiene-workflow/scripts/before.py` to inventory workflows and check name collisions.

### Stage 3: Execute

**Option A:** run `uv run skills/new-contact-hygiene-workflow/scripts/execute.py`, then open the created workflow in the UI and continue from step 3 below (copy actions, delay, branch). **Option B:** open HubSpot > Automation > Workflows > Create workflow, select "Contact-based", start from scratch, and follow all steps.

1. **Set enrollment trigger:**
   - Property: "Create date" > "is known"
   - This enrolls every new contact automatically.

2. **Add action: Set property value**
   - Property: "Lifecycle stage"
   - Value: "Lead"
   - Condition: Only if lifecycle stage is unknown (use an if/then branch before this step, or rely on HubSpot's "only if empty" option if available in your plan).

3. **Add action: Copy property**
   - Source: Associated company > "Company name"
   - Target: Contact > "Company" property

4. **Add action: Copy property**
   - Source: Associated company > "Industry"
   - Target: Contact > "Industry" property

5. **Add delay: a short delay (3-10 minutes, recommended: 5)**
   - Purpose: Allow time for company associations to sync (especially for form submissions or integrations that create contacts before associating them). Adjust the duration based on how quickly your integrations typically create associations.

6. **Add if/then branch:**
   - Condition: Contact "Company" property is unknown
   - YES branch: Add internal notification to CRM admin — "New contact {firstname} {lastname} ({email}) has no company association after enrichment attempt."
   - NO branch: No further action needed (contact is enriched).

7. **Review settings:**
   - Re-enrollment: OFF (each contact should only go through this once)
   - Unenrollment: None needed
   - Time zone: Not applicable (no time-based actions beyond delay)

8. **Turn on the workflow.**

### Stage 4: After

0. Run `uv run skills/new-contact-hygiene-workflow/scripts/after.py` (API path) to confirm the workflow exists and report enabled state.
1. Create a test contact manually. Confirm:
   - Lifecycle stage is set to "Lead"
   - Company name copied from associated company
   - Industry copied from associated company
2. Create a test contact with no company association. Confirm:
   - Admin notification fires after the configured delay
3. Check workflow history for any errors in the first 24 hours.

## Rollback

1. Turn off the workflow in HubSpot > Automation > Workflows.
2. Contacts already enriched retain their values — no destructive changes to undo.
3. If lifecycle stages were set incorrectly, use the Search API to find contacts created after the workflow activation date and reset as needed.

## Edge Cases

- **Contacts created via import:** These fire the trigger. If imports include company name/industry, the copy action will overwrite with the associated company's values. Consider excluding imported contacts via a list filter.
- **Contacts without company associations:** The copy action silently fails. The branch handles notification.
- **Multiple associated companies:** HubSpot copies from the primary associated company only.
