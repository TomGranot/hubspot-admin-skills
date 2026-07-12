---
name: lifecycle-progression-workflow
description: "Build workflows to automate contact progression through the sales funnel: Lead to MQL to SQL to Opportunity to Customer. Each transition is triggered by a specific event (score threshold, meeting booked, deal created, deal won)."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: automation-workflows
---

# Lifecycle Stage Progression Workflow

Automate the contact journey through the sales funnel with four progression workflows, each triggered by a specific business event.

## Progression Paths

| From | To | Trigger |
|------|----|---------|
| Lead | MQL | Lead score exceeds threshold |
| MQL | SQL | Meeting booked |
| SQL | Opportunity | Deal created and associated |
| Opportunity | Customer | Deal marked as closed-won |

## Prerequisites

- HubSpot Marketing Professional or Enterprise plan
- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with the `automation` scope (for the API path)
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- Lead scoring model configured (run `/build-lead-scoring` first) — you need the internal name of your score property
- Deal pipeline set up with a "Closed Won" stage
- Meeting tool or integration configured (for SQL transition)

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/lifecycle-progression-workflow/scripts/before.py` |
| Execute | [`scripts/execute.py`](./scripts/execute.py) | `uv run skills/lifecycle-progression-workflow/scripts/execute.py` |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run skills/lifecycle-progression-workflow/scripts/after.py` |

`before.py` inventories existing workflows and checks name collisions. `execute.py` creates all four progression workflows via `POST /automation/v4/flows` — **always disabled, for review before enabling**. `after.py` verifies and reports enabled state.

## Building the Workflow: Two Options

### Option A: Create via the v4 Automation API (primary)

All four progression workflows are linear (filter-based AND trigger → set lifecycle stage), which the v4 API expresses directly. The script encodes:

| Workflow | Enrollment (AND) | Action |
|----------|------------------|--------|
| Lead → MQL | score property >= threshold + stage = Lead | set stage = MQL |
| MQL → SQL | `engagements_last_meeting_booked` is known + stage = MQL | set stage = SQL |
| SQL → Opportunity | `num_associated_deals` >= 1 + stage = SQL | set stage = Opportunity |
| Opportunity → Customer | `hs_current_customer` = true + stage = Opportunity | set stage = Customer |

The last workflow uses `hs_current_customer` — the read-only system property HubSpot introduced in June 2026 that marks contacts belonging to a current customer — as a cleaner signal than inspecting associated deal stages.

**Before running:** set `LEAD_SCORE_PROPERTY` in `execute.py` to your score property's internal name. With HubSpot's post-2025 lead scoring tool, each score you create generates its own property — find the internal name under Settings > Properties (it is not the retired `hubspotscore`).

```bash
uv run skills/lifecycle-progression-workflow/scripts/before.py
uv run skills/lifecycle-progression-workflow/scripts/execute.py
```

**Safety model:** all four workflows are created with `isEnabled: false`. Review the triggers in the UI, add the optional internal-notification actions (marketing team, sales owner, CS/onboarding — recipients are portal-specific), then enable them one at a time, watching the first enrollments.

### Option B: Manual UI Build

Follow the step-by-step instructions in Stage 3 below. Use this on portals where the Automation API is unavailable, or when you prefer to configure the meeting/deal triggers with portal-specific event conditions instead of the property-based equivalents the script uses.

**Alternatives:** HubSpot Breeze AI can scaffold these workflows from prompts, but it creates event-based (OR) triggers where AND logic between the event and the current stage is required, and cannot configure re-enrollment — verify everything it builds. The Claude Chrome extension can drive the workflow builder UI directly. Both are secondary options.

## Step-by-Step Build Instructions

### Stage 1: Plan

1. Define your MQL score threshold (typically 40-60 on a 0-100 scale). Adjust after 30-60 days of observation.
2. Identify your lead score property's internal name (post-2025 scoring tool properties are per-score; see `/build-lead-scoring`).
3. Confirm your deal pipeline stages include a clear "Closed Won" equivalent.

### Stage 2: Before

1. Run `uv run skills/lifecycle-progression-workflow/scripts/before.py` to inventory workflows and check name collisions.
2. Document current lifecycle stage distribution (run the audit or check the property breakdown) so you can measure the impact.

### Stage 3: Execute

**Option A:** run `uv run skills/lifecycle-progression-workflow/scripts/execute.py`, then complete the UI review steps listed above.

**Option B — manual UI build:** build each as a separate contact-based workflow.

#### Workflow 1: Lead to MQL

1. **Trigger:** Your lead score property is greater than or equal to [threshold] AND lifecycle stage is "Lead"
2. **Action:** Set lifecycle stage to "Marketing Qualified Lead"
3. **Action (optional):** Send internal notification to marketing team
4. **Re-enrollment:** OFF

#### Workflow 2: MQL to SQL

1. **Trigger:** Meeting booked (use "Meeting activity date" is known, or "Number of meetings booked" is greater than 0) AND lifecycle stage is "Marketing Qualified Lead"
2. **Action:** Set lifecycle stage to "Sales Qualified Lead"
3. **Action (optional):** Send internal notification to sales owner
4. **Re-enrollment:** OFF

#### Workflow 3: SQL to Opportunity

1. **Trigger:** Associated deal is created (use "Number of associated deals" is greater than 0) AND lifecycle stage is "Sales Qualified Lead"
2. **Action:** Set lifecycle stage to "Opportunity"
3. **Re-enrollment:** OFF

#### Workflow 4: Opportunity to Customer

1. **Trigger:** Associated deal stage equals "Closed Won" AND lifecycle stage is "Opportunity"
2. **Action:** Set lifecycle stage to "Customer"
3. **Action (optional):** Send internal notification to CS/onboarding team
4. **Re-enrollment:** OFF

#### Workflow Settings (all four)

- Re-enrollment: OFF (lifecycle should only progress forward)
- Suppression list: None needed — the lifecycle stage condition prevents backwards movement
- Time zone: Not applicable

### Stage 4: After

0. Run `uv run skills/lifecycle-progression-workflow/scripts/after.py` (API path) to confirm all four workflows exist and report enabled state.
1. Test each workflow with a test contact:
   - Manually adjust score/create meeting/create deal/close deal and confirm progression.
2. Verify that workflows do not conflict — a contact should not be enrolled in two progression workflows simultaneously.
3. Check that lifecycle stages only move forward (HubSpot enforces this by default, but verify).
4. After one week, review the workflow history for each. Check for:
   - Contacts stuck at a stage despite meeting criteria
   - Unexpected enrollment volumes

## Rollback

1. Turn off any or all four workflows.
2. Lifecycle stages already set remain — HubSpot does not allow backward movement without manual override or a dedicated reset workflow.
3. If stages were set incorrectly, create a temporary workflow or use the API to reset affected contacts.

## Notes

- **Backward movement:** HubSpot prevents lifecycle stage from going backward by default. If a deal is lost and the contact should return to MQL, you need a separate "regression" workflow that explicitly sets the stage.
- **Multiple deals:** If a contact has multiple deals, the Opportunity-to-Customer workflow fires when any associated deal is closed-won. This is usually the desired behavior.
- **Score decay:** HubSpot's post-2025 scoring tool supports engagement decay, so a contact's score may drop below the MQL threshold after promotion. This is fine — the lifecycle stage is already set and will not regress.
