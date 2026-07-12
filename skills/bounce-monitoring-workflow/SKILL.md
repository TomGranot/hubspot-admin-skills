---
name: bounce-monitoring-workflow
description: "Build a workflow to protect sender reputation through automated bounce monitoring. Auto-suppresses contacts above a configurable bounce threshold, alerts on hard bounces, and flags high-bounce contacts for weekly manual review."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: automation-workflows
---

# Bounce Monitoring Workflow

Protect your email sender reputation with automated bounce detection and suppression. This workflow catches bounces as they happen rather than waiting for periodic cleanup.

## How It Works

| Condition | Action |
|-----------|--------|
| Hard bounce detected | Alert admin immediately, suppress contact |
| Suppression threshold reached (commonly 2-3 bounces) | Auto-suppress from marketing emails |
| Review threshold reached (commonly 3-5 bounces) | Flag for weekly manual review (delete vs. recover) |

## Prerequisites

- HubSpot Marketing Professional or Enterprise plan
- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with the `automation` scope (for the API path)
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- A custom contact property for review flagging (default: `email_health_flag` — the execute script creates it if missing)
- Admin email or Slack channel for hard bounce alerts

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/bounce-monitoring-workflow/scripts/before.py` |
| Execute | [`scripts/execute.py`](./scripts/execute.py) | `uv run skills/bounce-monitoring-workflow/scripts/execute.py` |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run skills/bounce-monitoring-workflow/scripts/after.py` |

`before.py` inventories existing workflows and checks name collisions. `execute.py` creates the `email_health_flag` property (if missing) and three bounce workflows via `POST /automation/v4/flows` — **always disabled, for review before enabling**. `after.py` verifies and reports enabled state.

## Building the Workflow: Two Options

### Option A: Create via the v4 Automation API (primary)

Instead of one workflow with three nested branches, the script decomposes the design into **three linear workflows** — the same coverage, cleanly expressible via the API and independently tunable:

1. **Hard Bounce Suppression**: enrollment = `hs_email_hard_bounce_reason_enum` is known. Actions: set `email_health_flag`, set marketing contact status to non-marketing.
2. **Suppress at N+ Bounces**: enrollment = `hs_email_bounce` >= suppression threshold (re-enrollment on). Action: set marketing contact status to non-marketing.
3. **Flag for Review at M+ Bounces**: enrollment = `hs_email_bounce` >= review threshold (re-enrollment on). Action: set `email_health_flag` (feeds `/review-bounced-contacts`).

Configure `SUPPRESSION_THRESHOLD` and `REVIEW_THRESHOLD` in `execute.py`, then:

```bash
uv run skills/bounce-monitoring-workflow/scripts/before.py
uv run skills/bounce-monitoring-workflow/scripts/execute.py
```

**Safety model:** all three workflows are created with `isEnabled: false`. During UI review: add the internal-notification actions (hard bounce alert, review alert — notification recipients are portal-specific), add "Set marketing contact status" manually if the script reported it had to omit it, then turn the workflows on.

### Option B: Manual UI Build (single workflow with nested branches)

Follow the step-by-step instructions in Stage 3 below — the original single-workflow design with three branch levels. Use this on portals where the Automation API is unavailable.

**Alternatives:** HubSpot Breeze AI can scaffold a similar workflow from a prompt, but it creates event-based (OR) triggers, cannot configure re-enrollment, and may flatten nested branches — verify everything it builds. The Claude Chrome extension can drive the workflow builder UI directly. Both are secondary options.

## Step-by-Step Build Instructions

### Stage 1: Plan

1. Choose your **suppression threshold** (commonly 2-3 bounces) and **review threshold** (commonly 3-5).
2. Decide who receives hard-bounce and review alerts.

### Stage 2: Before

1. Run `uv run skills/bounce-monitoring-workflow/scripts/before.py` to inventory workflows and check name collisions.
2. Identify your current bounce baseline — run a quick search for contacts where `hs_email_bounce` > 0 to understand the starting volume.
3. If building manually, create your bounce review property (checkbox or dropdown) — the API path creates it automatically.

### Stage 3: Execute

**Option A:** run `uv run skills/bounce-monitoring-workflow/scripts/execute.py`, then complete the UI review steps listed above.

**Option B — manual UI build:** build a single contact-based workflow with branching logic.

1. **Trigger:** `hs_email_bounce` is known (fires when bounce count updates)

2. **Branch 1: Hard bounce check**
   - Condition: `hs_email_hard_bounce_reason_enum` is known
   - **YES:**
     - Send internal notification: "Hard bounce: {email} — {hs_email_hard_bounce_reason_enum}"
     - Set `hs_marketable_status` to non-marketing (workflow action)
   - **NO:** Continue to Branch 2

3. **Branch 2: Bounce count >= your suppression threshold (commonly 2-3)**
   - Condition: `hs_email_bounce` is greater than or equal to your suppression threshold
   - **YES:**
     - Set `hs_marketable_status` to non-marketing (workflow action)
     - Continue to Branch 3
   - **NO:** No action (below threshold — monitor only)

4. **Branch 3: Bounce count >= your review threshold (commonly 3-5)**
   - Condition: `hs_email_bounce` is greater than or equal to your review threshold
   - **YES:**
     - Set your bounce review property = flagged
     - Send internal notification: "Contact {email} has [review threshold]+ bounces — review for deletion"
   - **NO:** No further action

5. **Settings:**
   - Re-enrollment: ON (contact should re-enter if bounce count increases)
   - Goal: None

6. **Turn on the workflow.**

### Stage 4: After

1. Run `uv run skills/bounce-monitoring-workflow/scripts/after.py` (API path) to confirm the workflows exist and report enabled state.
2. Check workflow history after the first week of email sends.
3. Review the flagged contacts list weekly — decide for each contact:
   - **Delete** if the email is clearly invalid (typo domain, defunct company)
   - **Attempt recovery** if the domain is valid (could be a temporary mailbox issue)
4. Monitor overall bounce rate in HubSpot email health dashboard.

## Rollback

1. Turn off the workflow.
2. Contacts already suppressed remain non-marketing. To reverse:
   - Filter contacts suppressed by this workflow (check your bounce review property or workflow history)
   - Manually set back to marketing contacts in the UI
3. Clear your bounce review property values in bulk if needed.

## Weekly Review Process

For contacts flagged at your review threshold:

1. Export the flagged contacts list.
2. For each contact, check:
   - Is the email domain still active? (Quick MX record check)
   - Is this a known customer or high-value contact?
   - Was the bounce recent or historical?
3. **Delete** contacts with invalid domains or clearly fake emails.
4. **Keep suppressed** contacts with valid domains but repeated soft bounces.
5. Clear the bounce review property after review.
