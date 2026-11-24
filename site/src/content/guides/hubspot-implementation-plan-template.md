---
title: 'HubSpot Implementation Plan Template (with Example)'
description: 'HubSpot implementation plan template: five phases, owners, a week-by-week timeline, effort per task and a worked example. Plus how to rescue a failed one.'
heading: 'HubSpot implementation plan template, with a worked example'
updated: 2026-11-25
order: 2
skills:
  - hubspot-implementation-plan
  - hubspot-audit
  - sandbox-self-test
---

A HubSpot implementation plan sequences the work so nothing is built on bad data. Clean first (weeks 1-2), fill data gaps (weeks 3-4), build segments and scoring (weeks 4-6), automate (weeks 6-8), then maintain on a schedule. Sales pipeline cleanup runs alongside the first two phases. Each task gets an owner, a trigger, an effort estimate and a status box.

Below is the template I use, a filled example, and a section on rescuing an implementation that went wrong. If you already have HubSpot running, the fastest way to fill the template is from a real audit: [install the skills](/install), run `/hubspot-audit`, then `/hubspot-implementation-plan`.

## What goes into a HubSpot implementation plan?

Five things per task: what triggers it, which phase it sits in, who owns it, how long it takes, and what it depends on. Without the dependency column, plans fail in a predictable way. Lead scoring gets built before industry data exists, so the scores are wrong from day one and nobody trusts them.

The order matters more than the dates. These are the dependencies I hold to:

- Company name before industry. Contact industry is copied from the company.
- Standardize country values before backfilling missing ones.
- Reassign records from people who left before assigning unowned ones.
- ICP tiers, then lead scoring, then smart lists, then campaign segment lists.
- Suppression workflows exist before suppression scripts run.

A word on scope. This template is for getting a HubSpot portal's CRM data and automation into working order: new portal or old one. It does not cover website or CMS builds, content migration or sales training.

## Who owns what in a HubSpot implementation?

Four roles cover most plans, even when one person wears several hats. The HubSpot admin owns the plan and the data work. Marketing ops owns suppression, scoring and segments. Sales ops and the reps own deal cleanup, because only the rep knows if a deal is dead. A Super Admin is needed for settings and integrations.

| Role                       | Owns                                                            |
| -------------------------- | --------------------------------------------------------------- |
| HubSpot admin (plan owner) | The plan, audits, data cleanup, enrichment, workflow builds     |
| Marketing ops              | Suppression rules, ICP definition, lead scoring, segment lists  |
| Sales ops + reps           | Pipeline design, deal review sessions, required deal properties |
| Super Admin                | Service keys, integrations, portal settings                     |

If deals sync from Salesforce, add the Salesforce admin. Do not touch synced deals or sync properties without them.

## HubSpot implementation plan template (copy this)

The template has five phases and one parallel track, laid out over eight weeks plus ongoing maintenance. Effort estimates are per task and come from the `/hubspot-implementation-plan` skill. Delete the rows your audit shows you don't need: if a dimension grades A, skip its tasks.

### Phase 1: Immediate hygiene (weeks 1-2)

Goal: stop paying for contacts you cannot email and protect sender reputation.

| #   | Task                                              | Owner             | Trigger                                 | Effort  | Status |
| --- | ------------------------------------------------- | ----------------- | --------------------------------------- | ------- | ------ |
| 1.1 | Delete contacts with no email                     | Admin             | Any contacts missing email              | 1 hr    | [ ]    |
| 1.2 | Suppress hard-bounced contacts                    | Marketing ops     | Any hard bounces                        | 1-2 hrs | [ ]    |
| 1.3 | Suppress global unsubscribes                      | Marketing ops     | Any global unsubscribes                 | 1-2 hrs | [ ]    |
| 1.4 | Suppress ghost contacts (delivered, never opened) | Marketing ops     | Never-opened count above your threshold | 2-3 hrs | [ ]    |
| 1.5 | Merge duplicate companies                         | Admin             | Duplicate domains found                 | 2-4 hrs | [ ]    |
| 1.6 | Reassign records from deactivated owners          | Admin + sales ops | Deactivated owners still own records    | 1-2 hrs | [ ]    |

Build the suppression workflow in the HubSpot UI before 1.2-1.4. Marketing contact status (`hs_marketable_status`) is read-only through the API. The workaround is a custom flag property set by script, and a workflow that switches flagged contacts to non-marketing.

### Phase 2: Data enrichment (weeks 3-4)

Goal: fill the gaps that block segmentation and scoring.

| #   | Task                                                        | Owner                 | Trigger                   | Effort  | Status |
| --- | ----------------------------------------------------------- | --------------------- | ------------------------- | ------- | ------ |
| 2.1 | Copy company name onto contacts from the associated company | Admin                 | Contacts missing company  | 1-2 hrs | [ ]    |
| 2.2 | Copy industry onto contacts from the company (after 2.1)    | Admin                 | Contacts missing industry | 1-2 hrs | [ ]    |
| 2.3 | Standardize country and state values                        | Admin                 | Inconsistent geo values   | 2-3 hrs | [ ]    |
| 2.4 | Backfill missing country and state (after 2.3)              | Admin                 | Missing geo data          | 2-3 hrs | [ ]    |
| 2.5 | Fix missing or wrong lifecycle stages                       | Admin + marketing ops | Missing or wrong stages   | 2-3 hrs | [ ]    |
| 2.6 | Assign unowned contacts (after 1.6)                         | Admin + sales ops     | Unowned contacts          | 1-2 hrs | [ ]    |

Lifecycle stage only moves forward in HubSpot. To move a contact back, clear the property first, then set the earlier stage.

### Phase 3: Segmentation and scoring (weeks 4-6)

| #   | Task                                                  | Owner         | Depends on | Effort  | Status |
| --- | ----------------------------------------------------- | ------------- | ---------- | ------- | ------ |
| 3.1 | Create ICP tier property and classification workflows | Marketing ops | Phase 2    | 3-4 hrs | [ ]    |
| 3.2 | Build the lead scoring model (in the UI)              | Marketing ops | 3.1        | 4-6 hrs | [ ]    |
| 3.3 | Build smart lists for core segments                   | Marketing ops | 3.2        | 2-3 hrs | [ ]    |
| 3.4 | Create campaign segment lists                         | Marketing ops | 3.3        | 1-2 hrs | [ ]    |

### Phase 4: Automation (weeks 6-8)

| #   | Task                                           | Owner             | Trigger                          | Effort  | Status |
| --- | ---------------------------------------------- | ----------------- | -------------------------------- | ------- | ------ |
| 4.1 | New contact hygiene workflow                   | Admin             | Always                           | 1-2 hrs | [ ]    |
| 4.2 | Engagement-based suppression (sunset) workflow | Marketing ops     | Engagement graded D or F         | 1-2 hrs | [ ]    |
| 4.3 | Lifecycle stage progression workflow           | Admin + sales ops | Always                           | 1-2 hrs | [ ]    |
| 4.4 | Bounce monitoring workflow                     | Marketing ops     | Deliverability graded C or worse | 1 hr    | [ ]    |
| 4.5 | Export all workflows to versioned JSON         | Admin             | After any workflow build         | 30 min  | [ ]    |

Build workflows disabled, review each one in the UI, then turn it on.

### Sales pipeline track (runs alongside weeks 1-4)

| #   | Task                                             | Owner     | Trigger                                  | Effort   | Status |
| --- | ------------------------------------------------ | --------- | ---------------------------------------- | -------- | ------ |
| S.1 | Reassign open deals from deactivated owners      | Sales ops | Orphaned open deals                      | with 1.6 | [ ]    |
| S.2 | Assign unowned SQL and Opportunity contacts      | Sales ops | Unowned sales-stage contacts             | 1-2 hrs  | [ ]    |
| S.3 | Fix past-due close dates and missing amounts     | Reps      | Deal data or hygiene graded C or worse   | 2-4 hrs  | [ ]    |
| S.4 | Review and close stale deals                     | Reps      | Open deals with no activity in 60+ days  | 2-3 hrs  | [ ]    |
| S.5 | Retire empty or over-staged pipelines            | Sales ops | Pipeline configuration graded C or worse | 1-2 hrs  | [ ]    |
| S.6 | Reconcile Opportunity contacts that have no deal | Admin     | Any found                                | 1-2 hrs  | [ ]    |

Run one review session per sales team. Do not bulk-close deals. Then lock in prevention: required properties per deal stage, pipeline rules and a stale-deal task workflow.

### Phase 5: Ongoing maintenance (week 9 onward)

| Task                                                             | Frequency | Effort       |
| ---------------------------------------------------------------- | --------- | ------------ |
| Weekly cleanup check                                             | Weekly    | 1 hr/week    |
| Review contacts with 3+ bounces                                  | Monthly   | 1 hr         |
| Clean up unused lists, forms and workflows                       | Monthly   | 1-2 hrs each |
| Clean up dashboards, stale deals, unused properties, lead owners | Quarterly | 1-3 hrs each |
| Re-run the audit                                                 | Quarterly | 1 hr         |

The [HubSpot admin checklist](/guides/hubspot-admin-checklist) breaks this cadence down by week, month and quarter.

### Effort summary

Add up the kept tasks in four buckets: fully scriptable, hybrid (script plus workflow), manual UI only, and ongoing hours per month. The total is your setup budget.

## HubSpot implementation plan example

Here is the template filled in for a hypothetical portal. It is an illustration, not a client. The audit grades are made up to show how grades decide which rows stay. Effort figures are the template's own.

**Audit result (hypothetical):** Deliverability D, Contact completeness C, Engagement D, Owner health B, Deal data quality C, Pipeline hygiene D, Pipeline configuration A.

| Week | Phase       | Kept tasks                       | Why kept                                                           | Effort                 |
| ---- | ----------- | -------------------------------- | ------------------------------------------------------------------ | ---------------------- |
| 1    | Phase 1     | 1.1, 1.2, 1.3                    | Deliverability D: billed contacts that cannot be emailed           | 3-5 hrs                |
| 1-2  | Phase 1     | 1.4, 1.6                         | Engagement D; Owner health B, but one rep left last month          | 3-5 hrs                |
| 1-2  | Sales track | S.1, S.3, S.4                    | Deal data C, Pipeline hygiene D                                    | 4-7 hrs + rep sessions |
| 3-4  | Phase 2     | 2.1, 2.2, 2.5                    | Completeness C, graded on missing lifecycle stage                  | 4-7 hrs                |
| 4-6  | Phase 3     | 3.1-3.4                          | Data now supports targeting                                        | 10-15 hrs              |
| 6-8  | Phase 4     | 4.1-4.5                          | 4.1 and 4.3 always; 4.2 for Engagement D; 4.4 for Deliverability D | 4.5-7.5 hrs            |
| 9+   | Phase 5     | Weekly check, quarterly re-audit | Keep it fixed                                                      | ~1 hr/week             |

Dropped: 1.5 (no duplicates flagged), 2.3-2.4 (geo values fine), S.5 (Pipeline configuration A). The plan is shorter because the audit said where not to spend time.

## How do you plan a HubSpot implementation from your own portal?

Run a read-only audit, then let it fill the template. The `/hubspot-implementation-plan` skill reads the audit report, keeps only the tasks the findings trigger, orders them by dependency, adds effort and automation type per task, and saves a plan with a checklist to `reports/`. It plans only what the audit measured.

```text
/plugin marketplace add tomgranot/hubspot-admin-skills
/plugin install hubspot-admin@hubspot-admin-skills
/hubspot-audit
/hubspot-implementation-plan
```

Own just one side of the portal? Run [`/hubspot-marketing-audit`](/skills/hubspot-marketing-audit) or [`/hubspot-sales-audit`](/skills/hubspot-sales-audit) instead. A marketing-scoped report gives a plan without the sales track, and the reverse. The full checklist behind the audit is in the [HubSpot audit checklist](/guides/hubspot-audit-checklist).

## How do you fix a failed HubSpot implementation?

Stop building and measure. Failed implementations rarely fail on one thing: scoring was built on incomplete data, workflows were edited with no record of what changed, deals were never closed out, and new contacts kept arriving dirty. Back up the workflows, run an audit, then restart the plan from Phase 1 instead of patching the top layer.

The signs I look for, and where each one leads:

| Symptom                               | Usual root cause                                                | Start here                                                                               |
| ------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Nobody trusts the forecast            | Open deals with no amount, past close dates, orphaned owners    | [Pipeline not trusted](/problems/hubspot-pipeline-forecast-not-trusted)                  |
| Lead scores mean nothing              | Scoring built before enrichment, or on retired score properties | [Lead scoring after 2025 changes](/problems/hubspot-lead-scoring-after-2025-changes)     |
| Lifecycle stages are wrong            | Stages set by hand, forward-only rule ignored                   | [Lifecycle stages wrong or missing](/problems/hubspot-lifecycle-stages-wrong-or-missing) |
| Data is dirty again a month later     | Cleanup without prevention workflows                            | [New contacts arrive dirty](/problems/hubspot-new-contacts-arrive-dirty)                 |
| A workflow broke and nobody knows why | No version history for workflows                                | [Workflows with no version control](/problems/hubspot-workflows-no-version-control)      |

The rescue order:

1. **Export every workflow first.** HubSpot has no recycle bin for workflows. [`/workflows-as-code`](/skills/workflows-as-code) saves each definition to JSON so you can diff and restore.
2. **Run the audit.** It is read-only, so it is safe on the portal that is already in trouble.
3. **Rebuild the plan from the findings**, starting at Phase 1, even if the portal is "live".
4. **Test destructive steps on a sandbox.** [`/sandbox-self-test`](/skills/sandbox-self-test) runs on a free developer test account and refuses to run against production.
5. **Add prevention before you call it done.** Required deal properties, the new contact hygiene workflow, the bounce monitor, and a weekly check.

## FAQ

### What does it cost?

The skills are free and open source under the MIT license. You need Claude Code and a HubSpot service key. The audits and hygiene skills work on any HubSpot tier. Workflow skills need Marketing Hub Professional or higher.

### Will running the plan break anything?

The audit and the plan generator only read. Skills that change data export a CSV of every affected record first, show what will change, ask before writing and stop at an abort threshold. Workflows are created switched off so you review them before they run. Deal cleanup creates review tasks for reps rather than closing deals.

### Do I need a developer?

No. Someone needs to create a service key (Settings > Integrations > Service Keys) and run Claude Code. Lead scoring and a few workflow steps are built in the HubSpot UI, and the skills walk you through them.

### Does this cover a HubSpot CMS implementation?

No. Website pages, blogs, themes and content migration are out of scope. This plan covers CRM data, segmentation and automation. If you are planning a CMS build, use a separate plan for the site and this one for the CRM it feeds.

### How long does a HubSpot implementation take with this plan?

The template runs over about eight weeks, plus maintenance at roughly an hour a week. Your total depends on which tasks your audit keeps. Deal cleanup is the least predictable part, because it depends on reps' time.

### Can I plan a brand-new implementation with it?

Yes, with a change of order. With no data yet, start with the decisions behind Phases 2-4: lifecycle stage definitions, required deal properties per stage, ICP criteria. Build the hygiene and bounce workflows before the first import, then run the audit after the import lands.

---

**Next step:** [install the skills](/install), run `/hubspot-audit`, then `/hubspot-implementation-plan`. You get this template filled in with your portal's real numbers.
