---
name: engagement-suppression-workflow
description: "Build a two-tier sunset workflow that re-engages dormant contacts before suppressing them. Tier 1 triggers a re-engagement campaign after a configurable inactivity window. Tier 2 suppresses contacts that fail to re-engage within a configurable re-engagement window."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: automation-workflows
---

# Engagement-Based Suppression Workflow

Build a two-tier sunset system that protects email deliverability while giving disengaged contacts a fair chance to re-engage before suppression.

## Why Two Tiers Matter

Suppressing contacts immediately after inactivity is aggressive and loses potential re-activations. A two-tier approach:
- **Tier 1** (inactive for your sunset window — typically 120-270 days): Triggers a re-engagement campaign — a last chance to interact.
- **Tier 2** (your re-engagement window after Tier 1 — typically 21-45 days — with still no engagement): Suppresses the contact from marketing emails.

This preserves deliverability scores while maximizing the recoverable audience.

## Prerequisites

- HubSpot Marketing Professional or Enterprise plan
- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with the `automation` scope (for the API path)
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- A re-engagement email campaign or sequence ready to send
- A custom dropdown property to track suppression status (default: `engagement_flag` — the execute script creates it if missing)

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/engagement-suppression-workflow/scripts/before.py` |
| Execute | [`scripts/execute.py`](./scripts/execute.py) | `uv run skills/engagement-suppression-workflow/scripts/execute.py` |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run skills/engagement-suppression-workflow/scripts/after.py` |

`before.py` inventories existing workflows and checks for name collisions. `execute.py` creates the `engagement_flag` property (if missing) and both sunset workflows via `POST /automation/v4/flows` — **always disabled, for review in the UI before enabling**. `after.py` verifies they exist and reports enabled state.

## Workflow Design

```
TRIGGER: Last engagement date > [sunset window] ago
         AND email is known
         AND not globally unsubscribed
         AND [suppression status property] is unknown
              │
              ▼
     ┌────────────────────┐
     │ Set [status prop]   │
     │ = "re-engagement    │
     │    sent"            │
     └────────┬───────────┘
              │
              ▼
     ┌────────────────────┐
     │ Enroll in           │
     │ re-engagement       │
     │ campaign/sequence   │
     └────────┬───────────┘
              │
              ▼
     ┌────────────────────┐
     │ Delay: [re-engage    │
     │  window] days       │
     └────────┬───────────┘
              │
              ▼
     ┌────────────────────┐
     │ IF/THEN BRANCH:     │
     │ Any engagement in   │
     │ re-engage window?   │
     ├──────────┬─────────┘
     │ YES      │ NO
     │          │
     ▼          ▼
   Clear     Set [status prop]
   status    = "suppressed"
   prop      + set non-marketing
```

## Building the Workflow: Two Options

### Option A: Create via the v4 Automation API (primary)

The stable v4 Automation API supports creating workflows programmatically. Instead of one workflow with an if/then branch, the script decomposes the design into **two linear workflows** — which the API expresses cleanly and which are easier to reason about:

1. **Tier 1 — Flag for Re-engagement**: enrollment = last open older than the sunset window (or never) AND email known AND not globally unsubscribed AND flag unknown. Action: set `engagement_flag` = "re-engagement sent".
2. **Tier 2 — Suppress Non-responders**: enrollment = flag = "re-engagement sent" AND still no open/click after sunset + re-engagement windows. Actions: set flag = "suppressed", set marketing contact status to non-marketing.

Run the scripts (configure `SUNSET_DAYS`, `REENGAGE_DAYS`, `FLAG_PROPERTY` in `execute.py` first):

```bash
uv run skills/engagement-suppression-workflow/scripts/before.py
uv run skills/engagement-suppression-workflow/scripts/execute.py
```

**Safety model:** both workflows are created with `isEnabled: false`. Review them in Automation > Workflows, then:
- Add the "enroll in re-engagement sequence/email" action to Tier 1 (email/sequence IDs are portal-specific).
- If the script reported it could not include the set-marketing-status action, add "Set marketing contact status" to Tier 2 in the UI (one click).
- Turn both on, choosing whether to enroll existing contacts.

**Payload notes:** the scripts use documented v4 action types (`0-5` set property; `0-31` set marketing contact status, with automatic fallback if your portal rejects its undocumented field shape). If a filter shape is rejected, HubSpot's own recommendation applies: build the workflow once in the UI, `GET /automation/v4/flows/{flowId}`, and adapt the script to the exact shapes your portal returns.

### Option B: Manual UI Build (single workflow with branch)

Follow the step-by-step instructions in Stage 3 below. This builds the original single-workflow design with the if/then re-engagement branch, and works on portals where the Automation API is unavailable.

**Alternatives:** HubSpot Breeze AI can scaffold a similar workflow from a prompt, but it creates event-based (OR) triggers instead of filter-based (AND) triggers and cannot configure re-enrollment or "is unknown" conditions — every Breeze-built trigger needs manual verification. The Claude Chrome extension can drive the workflow builder UI directly. Both are secondary to Options A and B.

## Step-by-Step Build Instructions

### Stage 1: Plan

1. Choose your **sunset window** (typically 120-270 days; default 180) and **re-engagement window** (21-45 days; default 30).
2. **Define "engagement"** for the Tier 2 check. Recommended: email open OR email click within the re-engagement window.
3. **Create or identify a re-engagement email/sequence.** A simple 1-2 email series asking "Still interested?" with a clear CTA works well.

### Stage 2: Before

Run `uv run skills/engagement-suppression-workflow/scripts/before.py` — it inventories all workflows, flags name collisions with the two planned SUNSET workflows, and writes the inventory CSV baseline.

If building manually, also create your suppression status property (dropdown: "re-engagement sent", "suppressed") if it does not exist — the API path creates it automatically.

### Stage 3: Execute

**Option A:** run `uv run skills/engagement-suppression-workflow/scripts/execute.py`, then complete the UI review steps listed above.

**Option B — manual UI build:**

1. **Set enrollment trigger:**
   - `hs_email_last_open_date` is more than your sunset window (typically 120-270 days) ago OR is unknown
   - AND `email` is known
   - AND `hs_email_optout` is not true
   - AND your suppression status property is unknown

2. **Action: Set contact property**
   - Your suppression status property = "re-engagement sent"

3. **Action: Enroll in re-engagement sequence** (or send re-engagement email)

4. **Delay: your re-engagement window (typically 21-45 days)**

5. **If/then branch:**
   - Condition: `hs_email_last_open_date` is less than [re-engagement window] days ago OR `hs_email_last_click_date` is less than [re-engagement window] days ago
   - **YES (re-engaged):** Set your suppression status property to blank/unknown (clears flag, contact returns to normal)
   - **NO (still disengaged):** Set your suppression status property = "suppressed" and set `hs_marketable_status` to non-marketing contact via the "Set marketing contact status" workflow action. (The property itself is read-only via direct API writes — a workflow action is the mechanism, whether the workflow is built in the UI or created via the v4 API.)

6. **Settings:**
   - Re-enrollment: OFF
   - Goal: Contact opens or clicks any email (optional — exits workflow early)

7. **Turn on the workflow.**

### Stage 4: After

1. Run `uv run skills/engagement-suppression-workflow/scripts/after.py` (API path) to confirm both workflows exist and report their enabled state.
2. Spot-check 10-20 contacts that entered the workflow. Confirm:
   - Re-engagement email was sent
   - After the re-engagement window, disengaged contacts were suppressed
   - Re-engaged contacts had their suppression status property cleared (Option B) or never entered Tier 2 (Option A)
3. Monitor deliverability metrics weekly for the first month.
4. Track how many contacts re-engage vs. get suppressed — adjust the sunset window if needed.

## Rollback

1. Turn off the workflow.
2. To reverse suppressions: filter contacts where your suppression status property = "suppressed" and manually set them back to marketing contacts in the UI.
3. Clear the suppression status property values in bulk if needed.

## Tuning

- **Shorten the sunset window** (e.g., 90-120 days) for aggressive deliverability improvement.
- **Lengthen the re-engagement window** (e.g., 45-60 days) if your email cadence is low.
- **Exclude recent customers** — add a filter to skip contacts with lifecycle stage = Customer or with a closed-won deal in the last 12 months.
