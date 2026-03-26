---
name: new-contact-hygiene-workflow
description: "Build a HubSpot workflow that auto-enriches and stages new contacts upon creation. Sets lifecycle stage, copies company name and industry from associated company, and branches on completeness. Must be built manually in the HubSpot UI due to API limitations."
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: automation-workflows
---

# New Contact Hygiene Workflow

Build a workflow that automatically enriches every new contact at creation time. This ensures contacts enter the database with a lifecycle stage, company name, and industry before any human touches them.

## Why This Cannot Be Fully Automated via API

Three HubSpot API limitations prevent full automation:

1. **"Is unknown" branch conditions** are not supported programmatically — the Workflows API cannot create branches that check whether a property has never been set.
2. **Copy from associated object** actions (e.g., copy company name from the associated company) are not available via API.
3. **Workflows API v4 is beta** and unstable — production workflows should not depend on it.

You have three options for building this workflow, described below.

## Building the Workflow: Three Options

### Option 1: Manual UI Build

Follow the step-by-step instructions in the "Execute" section below. This is the most reliable method and gives you full control over every trigger, branch, and action.

### Option 2: HubSpot Breeze AI

HubSpot's built-in Breeze AI can generate a workflow skeleton from a natural language prompt. Navigate to **Automation > Workflows > Create workflow > "Describe what you want"** and paste the following prompt:

```
Create a contact-based workflow that triggers when a contact is created. It should:
1. Set the lifecycle stage to "Lead" if it is empty
2. Copy the company name from the associated company to the contact's Company property
3. Copy the industry from the associated company to the contact's Industry property
4. Wait a short delay (3-10 minutes, recommended: 5)
5. Check if the contact's Company property is still empty — if yes, send an internal notification to the admin saying the contact has no company association
```

**CRITICAL WARNING: Breeze trigger limitations.** Breeze creates **event-based triggers (OR logic)** instead of **filter-based triggers (AND logic)**. After Breeze creates the workflow, you MUST manually verify and fix the trigger/enrollment conditions in the UI. Breeze is best used for creating the workflow skeleton (actions, branches, delays) -- the trigger conditions almost always need manual correction.

**Additional Breeze limitations for this workflow:**
- Breeze **cannot** create "is unknown" branch conditions -- you must add these manually
- Breeze **cannot** create "copy property from associated object" actions -- you must add these manually
- Breeze **cannot** configure re-enrollment rules

Given these limitations, Breeze provides minimal value for this particular workflow. Manual build (Option 1) is recommended.

### Option 3: Claude Anthropic Chrome Extension

The Claude Anthropic Chrome extension lets Claude see and interact with the HubSpot workflow builder UI directly. You can describe the workflow logic in natural language and Claude will click through the UI to build it. This is often more accurate than Breeze for complex workflows because Claude can verify each step visually, including "is unknown" branch conditions and copy-from-association actions that Breeze cannot handle.

To use this approach:
1. Open the HubSpot workflow builder in Chrome (Automation > Workflows > Create workflow)
2. Activate the Claude Chrome extension
3. Describe the workflow using the design diagram and instructions from this skill

> **Note on Fast Mode**: If you're using Claude Code's Fast Mode to speed up workflow creation,
> be aware of the billing model: Haiku usage is included in your subscription, but Opus in
> Fast Mode consumes extra credits. For workflow building tasks (which are UI-heavy and may
> require many interactions), consider whether the speed tradeoff is worth the credit cost.

## Prerequisites

- HubSpot Marketing Professional or Enterprise plan
- Workflow creation permissions in HubSpot
- Company association enrichment completed (run `/enrich-company-name` and `/enrich-industry` first for existing contacts)

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

### Stage 1: Before — Verify Prerequisites

1. Confirm company enrichment processes have run for existing data.
2. Open HubSpot > Automation > Workflows > Create workflow.
3. Select "Contact-based" workflow, start from scratch.

### Stage 2: Execute — Build the Workflow

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

### Stage 3: After — Verify

1. Create a test contact manually. Confirm:
   - Lifecycle stage is set to "Lead"
   - Company name copied from associated company
   - Industry copied from associated company
2. Create a test contact with no company association. Confirm:
   - Admin notification fires after the configured delay
3. Check workflow history for any errors in the first 24 hours.

### Stage 4: Rollback

1. Turn off the workflow in HubSpot > Automation > Workflows.
2. Contacts already enriched retain their values — no destructive changes to undo.
3. If lifecycle stages were set incorrectly, use the Search API to find contacts created after the workflow activation date and reset as needed.

## Edge Cases

- **Contacts created via import:** These fire the trigger. If imports include company name/industry, the copy action will overwrite with the associated company's values. Consider excluding imported contacts via a list filter.
- **Contacts without company associations:** The copy action silently fails. The branch handles notification.
- **Multiple associated companies:** HubSpot copies from the primary associated company only.
