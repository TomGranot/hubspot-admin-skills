---
name: hubspot-sales-audit
description: "Audit the sales side of a HubSpot portal: pipeline configuration, deal data quality, stale and past-due deals, ownership and handoff gaps, and overdue follow-up. Read-only. Use when the forecast is not trusted, before a pipeline redesign or a new sales leader's first review, or when reps and reports disagree about what is in the pipeline."
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: audit-planning
---

# HubSpot Sales Audit

A read-only audit of everything sales operations owns in a HubSpot portal. It answers one question from several angles: can anyone trust what the pipeline says?

## Why This Matters

A forecast is a sum over deal records. If a fifth of open deals have no amount, a quarter have close dates in the past, and some belong to reps who left months ago, the forecast is wrong before anyone applies judgment to it. Pipeline reviews then turn into data-entry sessions, and leaders stop using the CRM to make decisions. Most of this is measurable in a few minutes, and most of it is fixable.

## How It Relates to the Other Audits

This skill is a lens on the same engine that powers `/hubspot-audit` and `/hubspot-marketing-audit`. It runs the **shared** dimensions (database size, owner health, company data, duplicates) plus the **sales** dimensions, and skips deliverability and engagement entirely. Because the shared dimensions are computed by the same code under every scope, the numbers here match what the marketing team sees in their audit.

| If you own | Run |
|------------|-----|
| Sales only | this skill |
| Marketing only | `/hubspot-marketing-audit` |
| The whole portal | `/hubspot-audit` (both lenses in one report) |

## Prerequisites

- The `hubspot-audit` skill installed alongside this one (it ships the engine)
- `HUBSPOT_ACCESS_TOKEN` in `.env`, with read scopes for deals, contacts, companies, and owners. Add read scopes for tasks and leads to fill in the Activity & Follow-up dimension
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)

The audit runs on any HubSpot tier with deals. The leads object needs Sales Hub; without it those rows show `n/a`.

## Run It

The engine lives in the `hubspot-audit` skill, one directory over from this one. Run it from your project directory so `.env` and `reports/` resolve there (in a clone of the repo the path is `skills/hubspot-audit/scripts/audit_portal.py`).

```bash
uv run ../hubspot-audit/scripts/audit_portal.py --scope sales
```

Output: `reports/hubspot-sales-audit-{YYYY-MM-DD}.md` and a `.json` twin.

## What It Measures

| Dimension | Metrics | Graded on |
|-----------|---------|-----------|
| Pipeline Configuration | Number of pipelines, deals (and open deals) per pipeline, pipelines with zero deals, pipelines with more than 10 open stages | empty + bloated pipelines |
| Deal Data Quality | Open deals missing amount, close date, owner, or any associated contact; closed-lost deals with no loss reason | missing amount + close date |
| Pipeline Hygiene & Velocity | Open deals with no logged activity in 60+ days, open deals whose close date has passed, open deals with no next activity; deals closed and win rate over the last 90 days | stale + past-due deals |
| Sales Ownership & Handoff | Open deals owned by deactivated users; SQL and Opportunity contacts with no owner; Opportunity-stage contacts with no deal | orphaned deals + unowned sales-stage contacts |
| Activity & Follow-up | Open tasks, overdue open tasks, leads, leads with no owner | overdue tasks |
| *Shared:* Owner Health, Company Data, Database Size, Duplicates | see `/hubspot-audit` | |

Thresholds are constants in the script's `# --- Configuration ---` block: `STALE_DEAL_DAYS` (60), `WIN_RATE_WINDOW_DAYS` (90), `MAX_STAGES_PER_PIPELINE` (10). Set them to match your sales cycle before reading the grades. A 60-day stale window is strict for enterprise deals and generous for transactional ones.

## Reading the Results

1. **Past-due close dates come first.** An open deal with a close date in the past is wrong by definition: it either closed, slipped, or died, and the record says none of those. This is the cheapest forecast fix available.
2. **Stale is a conversation, not a deletion.** No logged activity in 60 days can mean a dead deal or a rep who does not log. Check a sample (the MCP server is good for this, see `/connect-hubspot-mcp`) before deciding which problem you have. The fixes are different: one is pipeline cleanup, the other is activity capture.
3. **Missing amounts skew weighted pipeline more than missing deals.** A deal with no amount contributes zero to every weighted report. If early stages legitimately have no amount yet, make amount conditionally required from the stage where it should exist.
4. **Orphaned open deals are P0.** A deal owned by a deactivated user gets no follow-up and appears in nobody's forecast. Reassign before anything else.
5. **Handoff gaps show where marketing and sales disagree.** SQL or Opportunity contacts with no owner mean routing broke. Opportunity-stage contacts with no deal mean lifecycle stage is being set by hand or by a workflow that does not create deals. Share these two rows with marketing ops: the root cause usually sits on their side of the line.
6. **Loss reasons are the cheapest win/loss data you will ever get.** If most closed-lost deals have none, make the property required on the Closed Lost stage.
7. **Win rate is context.** It is reported so the other numbers can be read against it and does not affect any grade. A healthy win rate on a pipeline full of stale deals usually means the losses are never being closed out.

## From Findings to Fixes

| Order | Skill | Fixes |
|-------|-------|-------|
| 1 | `/reassign-deactivated-owners` | Open deals and contacts owned by people who have left |
| 2 | `/assign-unowned-contacts` | Sales-stage contacts nobody is working |
| 3 | `/cleanup-deals` | Missing amounts and close dates, stale and past-due deals, test deals, unused pipelines |
| 4 | `/cleanup-lead-owners` | Unowned companies, deals, and leads; non-employee users |
| 5 | `/fix-lifecycle-stages` | Opportunity-stage contacts with no deal; customers at the wrong stage |
| 6 | `/lifecycle-progression-workflow` | Handoff automation, so the gaps do not reopen |
| 7 | `/merge-duplicate-companies` | Duplicate accounts splitting deal history |

Run `/hubspot-implementation-plan` to turn the report into a phased plan.

Prevention matters more than cleanup here. Three portal settings stop most of what this audit finds, and all three are configured in the HubSpot UI: required properties per deal stage (Settings > Objects > Deals > Pipelines), pipeline rules that restrict skipping stages and backward movement, and a workflow that creates a task for the owner when an open deal has had no activity for your stale window.

## What This Audit Does Not Cover

- **Forecast accuracy and time in stage.** HubSpot's forecast tool and pipeline reports own these. Forecast submissions are readable by API on Sales Hub Professional and above (`crm.objects.forecasts.read`) if you want to extend the engine.
- **Sequences.** The Sequences API only works with user-level authentication, so an account-level token cannot audit enrollment.
- **Rep performance.** The audit measures data quality, not people. Per-owner breakdowns are a deliberate omission: add them only if the team has agreed how they will be used.
- **Quotes, products, and line items.** Out of scope for now.

## Rollback

Nothing to roll back: the audit only reads. To remove its output, delete the files it wrote under `reports/`.
