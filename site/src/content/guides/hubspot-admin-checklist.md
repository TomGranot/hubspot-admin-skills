---
title: 'HubSpot Admin Checklist: Weekly, Monthly, Quarterly'
description: 'HubSpot admin checklist and maintenance routine: weekly, monthly, quarterly and twice-yearly tasks, with thresholds, workflow upkeep and skills to script it.'
heading: 'HubSpot admin checklist: weekly, monthly and quarterly maintenance'
updated: 2026-11-25
order: 5
skills:
  - weekly-cleanup-routine
  - quarterly-database-cleanup
  - cleanup-workflows
---

HubSpot administration is mostly maintenance on a cadence. Weekly: a five-minute check of bounces, new contacts, workflow errors, list trends and a data sample. Monthly: bounced-contact review and cleanup of unused lists, forms and workflows. Quarterly: a full re-audit plus deals, properties, dashboards and owners. Twice a year: check which integrations call retiring API versions.

Cleanups create a clean moment, not a clean system. Portals drift back within weeks without a routine. Below is the routine I run, with the thresholds that tell you when to act. Every item can be done by hand. If you'd rather script the parts that can be scripted, [install the skills](/install).

## What does a HubSpot admin do?

A HubSpot admin keeps the portal's data, automation and access trustworthy. In practice that means four jobs: keep bad data out (bounces, records with no email, contacts with no owner), keep automation working (workflows, lists, forms), keep the structure lean (properties, pipelines, dashboards), and keep access and integrations current (departing users, API versions, service keys).

Everything below falls into one of those four buckets. The rest of the job, like building campaigns or reports for other teams, sits on top of this. It goes badly when this layer is neglected.

## As it happens: event-driven admin tasks

Some admin work has no calendar. It is triggered by something happening in the business, and it should happen that day, not at the next weekly check. Three triggers cover most of it: someone leaves the company, a large import or new integration lands, and someone edits a production workflow.

| Trigger                                   | Do this                                                                                                                                 | Skill                                                                |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| A user is deactivated                     | Reassign their contacts, companies and open deals to an active owner. Orphaned open deals get no follow-up and sit in nobody's forecast | [reassign-deactivated-owners](/skills/reassign-deactivated-owners)   |
| A large import or new integration         | Spot-check 5-10 of the new records for email, company and lifecycle stage. Trace any bad ones to their source                           | [new-contact-hygiene-workflow](/skills/new-contact-hygiene-workflow) |
| A workflow is edited or deleted           | Export workflow definitions so you can diff and restore. HubSpot has no recycle bin for workflows                                       | [workflows-as-code](/skills/workflows-as-code)                       |
| Hard-bounce alert from the bounce monitor | Find the source: a bad import or form spam                                                                                              | [bounce-monitoring-workflow](/skills/bounce-monitoring-workflow)     |

## Weekly HubSpot maintenance checklist (5 minutes)

The weekly check is a spot-check, not an audit. Run it every Monday morning in a 15-minute calendar block: five minutes for the checks, ten for follow-up. Open three views first: the email health dashboard, the workflow dashboard and the contacts list sorted by create date, newest first. Then do five one-minute checks.

- [ ] **Bounces.** How many contacts did the bounce monitoring workflow flag this week? **More than 10:** find the source (bad import? form spam?). **Zero:** confirm the workflow is still switched on.
- [ ] **New contact quality.** Filter contacts created in the last 7 days. Spot-check 5-10 for a valid email, company name and lifecycle stage. If quality is low, find which form, import or integration created them.
- [ ] **Workflow health.** On the workflow dashboard, look for workflows showing errors, workflows with zero enrollments that should be active, and workflows someone switched off by accident.
- [ ] **List trends.** Check your key lists: customers, MQLs, suppressed. A sudden jump in suppressed contacts can mean a deliverability problem.
- [ ] **Data sample.** Pull 10 random contacts. Check email, company, lifecycle stage and owner. **More than 2 of 10 with gaps:** flag it for a deeper review.

Log each week in a simple table:

```text
Date       | Bounces flagged | New contact quality | Workflow issues | List anomalies | Data quality
YYYY-MM-DD | X               | Good / Bad          | None / details  | None / details | X/10 complete
```

The rule that makes the log worth keeping: **escalate anything that shows up two weeks in a row.** If you miss a week, skip it. Don't double up.

The weekly check assumes a bounce monitoring workflow is running. Set that up first with [`/bounce-monitoring-workflow`](/skills/bounce-monitoring-workflow). The full routine is the [`/weekly-cleanup-routine`](/skills/weekly-cleanup-routine) skill.

## Monthly HubSpot maintenance checklist

Monthly work removes what accumulated: contacts that keep bouncing, and lists, forms and workflows nobody uses any more. Each task has a clear rule for what counts as unused, and each one is checked against dependencies before anything is deleted. Budget an hour or two per item.

- [ ] **Review contacts with 3+ bounces.** For each one, decide: delete, or attempt recovery. Deleted contacts can be restored from HubSpot's recycling bin within 90 days. [review-bounced-contacts](/skills/review-bounced-contacts) is written as a weekly review. Monthly is the minimum; go weekly if the bounce monitor flags a lot.
- [ ] **Lists.** Candidates: zero members and created more than 30 days ago, not used by any workflow or email, or overlapping criteria. A list with zero members can still be a workflow enrollment trigger, so cross-check first. [cleanup-lists](/skills/cleanup-lists)
- [ ] **Forms.** Candidates: zero submissions and created more than 30 days ago, not embedded on any page, or test forms. [cleanup-forms](/skills/cleanup-forms)
- [ ] **Workflows.** Candidates: turned off for 90+ days with no plan to reactivate, zero enrollments ever, or test workflows. [cleanup-workflows](/skills/cleanup-workflows)

Before any monthly cleanup, ask one question: is anything on the list protected? Suppression lists, compliance segments, legal forms and integration workflows stay, whatever their numbers say.

## HubSpot workflow maintenance

Workflow maintenance means three things: catching errors weekly, retiring dead workflows monthly, and keeping a backup of every definition. The backup is the one most portals skip. One wrong click in the workflow editor can break lead routing or suppression for weeks, and HubSpot has no recycle bin for workflows.

What I do:

1. **Weekly:** scan the workflow dashboard for errors and for workflows that were switched off.
2. **Monthly:** retire workflows that have been off for 90+ days or never enrolled anyone.
3. **After every change:** export all workflows to JSON with [`/workflows-as-code`](/skills/workflows-as-code). Keep the exports in a private git repository so you can diff what changed and restore a broken workflow.
4. **For new workflows:** create them switched off, review them in the UI, then turn them on.

If someone has already edited a workflow and nobody knows what changed, see [workflows with no version control](/problems/hubspot-workflows-no-version-control).

## Quarterly HubSpot admin checklist

The quarterly sweep is the deep review. Re-run the full audit, compare every number with last quarter, and act on anything that got worse by more than 5 percentage points. Then clean the slower-moving parts of the portal: deals, properties, dashboards and owners. Do it on the first Monday of each quarter, and review last quarter's action items before you start.

### Re-audit and compare

- [ ] Run [`/hubspot-audit`](/skills/hubspot-audit) for fresh numbers. Or have each team run [`/hubspot-marketing-audit`](/skills/hubspot-marketing-audit) and [`/hubspot-sales-audit`](/skills/hubspot-sales-audit).
- [ ] **Data quality:** missing email, company, industry, country, lifecycle stage. Flag any property whose completeness dropped by more than 5%.
- [ ] **Bounces:** contacts with 1, 2 and 3+ bounces; hard bounce rate against last quarter.
- [ ] **Engagement:** active contacts (engaged in the last 90 days) and zombie contacts (no engagement in 6+ months), as a share of the total.
- [ ] **Scoring calibration:** look at the lead score distribution. Check MQL conversion. **Below 10% or above 50%:** adjust the scoring model.
- [ ] **Lists:** total, unused, duplicate or overlapping.

### Clean the slow-moving parts

- [ ] **Deals.** Past-due close dates, no activity in 60+ days, missing amounts, closed-lost with no reason, likely test deals. Send each rep their flagged deals as one review task. Don't bulk-close. [cleanup-deals](/skills/cleanup-deals)
- [ ] **Properties.** Custom properties with zero populated records and no use in any form, workflow or list, plus "test", "temp", "old\_" and "copy_of" names. Archive first, delete after 30 days. Leave Salesforce sync properties to the Salesforce admin. [cleanup-properties](/skills/cleanup-properties)
- [ ] **Dashboards.** Not viewed in 90+ days (ask the owner first), duplicates, and default dashboards nobody customized. There is no dashboard API, so this one is manual, under Reports > Dashboards. [cleanup-dashboards](/skills/cleanup-dashboards)
- [ ] **Lead owners.** Remove non-employee users and reassign what they own. [cleanup-lead-owners](/skills/cleanup-lead-owners)

Save the results as a dated report with a last-quarter vs. this-quarter table and an owner and deadline for each action item. [`/quarterly-database-cleanup`](/skills/quarterly-database-cleanup) generates that report.

## Twice a year: integrations and API versions

Every six months, check what calls HubSpot's APIs and which versions they use. HubSpot releases a new date-based API version every March and September. v4 endpoints lose support on March 30, 2027. v1-v3 have been unsupported since September 15, 2026, with enforcement in September 2027, the same deadline for moving legacy private apps to service keys.

- [ ] Open each legacy private app's **Logs** under Settings > Integrations > Private Apps. The request paths show the API version.
- [ ] List connected apps and ask vendors of business-critical ones about their migration.
- [ ] Search internal code and custom middleware steps for `/v1/` to `/v4/` HubSpot paths.
- [ ] Give every caller an owner and a migration date.

[audit-api-usage](/skills/audit-api-usage) walks through it. Background is on the [2027 API deadline page](/problems/hubspot-api-versions-2027-deadline).

## The whole HubSpot admin checklist on one page

| Cadence       | Task                                                                               | Time                 |
| ------------- | ---------------------------------------------------------------------------------- | -------------------- |
| As it happens | Reassign departing users' records; check new imports; export workflows after edits | Minutes each         |
| Weekly        | Bounces, new contacts, workflow errors, list trends, 10-record sample              | 5 min (15 min block) |
| Monthly       | 3+ bounce review; unused lists, forms, workflows                                   | 1-2 hrs per item     |
| Quarterly     | Full re-audit and trend comparison; deals, properties, dashboards, lead owners     | 1-3 hrs per item     |
| Twice a year  | API version and integration inventory                                              | An afternoon         |

Starting from a messy portal rather than a clean one? Do the cleanup before the cadence. The [HubSpot audit checklist](/guides/hubspot-audit-checklist) shows what to measure, and the [implementation plan template](/guides/hubspot-implementation-plan-template) puts the fixes in order.

## FAQ

### What does scripting this cost?

The skills are free and open source under the MIT license. You need Claude Code, a HubSpot service key, and Python 3.10+ with `uv` for the scripted skills. The audits and hygiene skills work on any HubSpot tier. Workflow skills need Marketing Hub Professional or higher.

### Can the scripts break my portal?

The audits and checks only read. Skills that change data export a CSV of every affected record first, show you what will change, ask before writing and stop at an abort threshold. Workflows are created switched off. To see it work before trusting it, run [`/sandbox-self-test`](/skills/sandbox-self-test) on a free HubSpot developer test account.

### Do I need a developer to maintain HubSpot?

No. The weekly check is five minutes in the HubSpot UI. The scripted skills need someone who can create a service key and run Claude Code, not someone who writes code.

### Where does my CRM data go?

Nowhere new. The scripts run on your machine and call HubSpot's API with your own service key. CSV exports stay in a local, gitignored folder.

### What is this checklist not for?

It does not cover website or CMS upkeep, campaign performance, user training or permission design. It is about keeping CRM data, automation and integrations healthy.

### How do I know the routine is working?

Watch the weekly log and the quarterly trend table. Fewer weekly flags, and quarterly numbers that hold steady or improve, mean it's working. If the same issue shows up two weeks in a row, escalate it. It needs a fix, not another check.

## Want someone to do this for you?

I help companies install these skills and run them on their own portal: the first audit, the cleanup it prescribes, and the weekly routine after it. You keep the scripts, the CSV audit trail and the routine. If you would rather hand it off, [email me](mailto:tom@granot.io) with a line about your portal.

---

**Next step:** [install the skills](/install) and put `/weekly-cleanup-routine` on your Monday calendar.
