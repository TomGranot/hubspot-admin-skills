---
title: 'HubSpot Audit Checklist: Marketing, Sales and Data'
description: 'HubSpot audit checklist: the checks, thresholds and grades for deliverability, data, pipelines, owners and integrations. Run it by hand or with a free script.'
heading: 'HubSpot audit checklist: what to check, and what counts as a fail'
updated: 2026-11-25
order: 1
skills:
  - hubspot-audit
  - hubspot-marketing-audit
  - hubspot-sales-audit
---

A HubSpot audit is a count of what is broken in your portal, area by area. For each area you measure the share of records affected: bounced and unsubscribed contacts, missing lifecycle stages, unowned records, open deals with no amount or a past close date, stale deals, overdue tasks. Then you grade each share and fix the worst first.

Below is the checklist I use, with the exact property and threshold behind each check. You can run every check by hand in the HubSpot UI. If you would rather not, there is a free, read-only script that runs all of them in minutes. [Install the skills](/install) and run `/hubspot-audit`.

## How do you audit a HubSpot portal?

Count, grade, then prescribe. Work through four areas: shared data (owners, companies, duplicates), marketing (deliverability, completeness, engagement, assets), sales (pipelines, deal quality, stale deals, handoff, follow-up) and integrations (which apps call which API versions). For each check, divide affected records by the total and grade the result.

The grading scale I use is the one built into the audit script:

| Grade | Share of records affected | Meaning                                      |
| ----- | ------------------------- | -------------------------------------------- |
| A     | under 5%                  | Healthy                                      |
| B     | 5-15%                     | Minor issues                                 |
| C     | 15-30%                    | Needs attention                              |
| D     | 30-50%                    | Significant problems                         |
| F     | over 50%                  | Critical                                     |
| ?     | could not be read         | Fix access and re-run. Not the same as clean |

Treat a grade as a starting point. A portal with 40 open deals and 3 stale ones is in a different place from one with 4,000 and 300, even though both grade B.

The implementation plan treats a grade of C or worse as the trigger for cleanup work on several dimensions. That is a sensible line between "fine" and "fix it".

## Shared checks: owners, company data, duplicates

Shared checks are the ones both marketing and sales care about: who owns each record, whether company records are complete, and whether accounts are duplicated. Run them first. Their answers feed every other area, and a marketing audit and a sales audit should agree on these numbers.

| Check                               | How to find it                                                                             | Graded on                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| Total contacts, companies, deals    | Object index counts                                                                        | Not graded. This is your denominator                    |
| Contacts with no owner              | Filter: Contact owner is unknown                                                           | Unowned + orphaned contacts, as a share of all contacts |
| Contacts owned by deactivated users | Filter by each deactivated user as owner                                                   | (same grade as above)                                   |
| Companies with no owner             | Filter: Company owner is unknown                                                           | Reported, not graded                                    |
| Companies missing domain            | Filter: Company domain name is unknown                                                     | Share of all companies                                  |
| Companies missing industry, country | Filter: is unknown                                                                         | Reported, not graded                                    |
| Duplicate companies                 | Contacts > Actions > Manage duplicates for contacts; company duplicates need a domain scan | Flagged, not counted                                    |

One gotcha: in the API, deactivated owners only show up when you ask for archived owners. If you count by hand, list your offboarded users first.

Fixes: [reassign deactivated owners](/skills/reassign-deactivated-owners), [assign unowned contacts](/skills/assign-unowned-contacts), [merge duplicate companies](/skills/merge-duplicate-companies).

## Marketing audit checklist: deliverability, data, engagement, assets

A HubSpot marketing audit answers three questions. Can we reach the people in this database? Do we know enough about them to segment? How much of what we pay for is dead weight? Count bounced, unsubscribed and never-engaged contacts, then the gaps that block segmentation, then the lists, workflows and forms piling up.

### Email deliverability

| Check                 | Property                                    | Graded on                                                      |
| --------------------- | ------------------------------------------- | -------------------------------------------------------------- |
| Marketing contacts    | `hs_marketable_status` = true               | Not graded                                                     |
| Hard bounced          | `hs_email_hard_bounce_reason_enum` is known | Hard bounces + global unsubscribes, as a share of all contacts |
| Globally unsubscribed | `hs_email_optout` = true                    | (same grade)                                                   |
| 3+ bounces            | `hs_email_bounce` >= 3                      | Reported                                                       |
| Never emailed         | `hs_email_last_send_date` is unknown        | Reported                                                       |

Hard-bounced and unsubscribed contacts that are still marketing contacts are pure cost. Fix those first. See [hard bounces hurting deliverability](/problems/hubspot-hard-bounces-hurting-deliverability) and [paying for contacts you cannot email](/problems/hubspot-marketing-database-health-check).

### Contact data completeness

Count contacts missing email, lifecycle stage, company, industry, country and job title. The grade uses missing lifecycle stage.

Read these gaps against how you actually segment. A missing job title only matters if lists, scoring or routing use it.

Contacts with no email at all can never be emailed and still count toward your bill. [Delete them](/skills/delete-no-email-contacts) before anything else.

### Engagement health

| Check                                   | Property                                                         | Graded on             |
| --------------------------------------- | ---------------------------------------------------------------- | --------------------- |
| Opened in the last 90 days              | `hs_email_last_open_date` within 90 days                         | Not graded            |
| Never opened any email                  | `hs_email_last_open_date` is unknown                             | Share of all contacts |
| Last open over 365 days ago             | `hs_email_last_open_date` older than 365 days                    | Reported              |
| Current customers not at Customer stage | `hs_current_customer` = true and lifecycle stage is not Customer | Reported              |

Two warnings. "Never opened" is stored as an empty property, not as 0, so filter on "is unknown". A filter for "equals 0" returns nothing.

And separate "never emailed" from "never opened". Never emailed is often fine. Never opened after 5 to 15 delivered emails is a [ghost contact](/problems/hubspot-ghost-contacts-never-engaged). Apple Mail Privacy Protection also inflates opens, so lean on clicks when deciding who to sunset.

### Lists, workflows and forms

Count total lists, active and inactive workflows, and forms. The audit does not grade these, because whether 300 lists is sprawl depends on the team.

The cleanup thresholds I use:

- **Lists:** zero members and created more than 30 days ago. Check it is not a workflow enrollment trigger first.
- **Forms:** zero submissions and created more than 30 days ago.
- **Workflows:** turned off for 90+ days, or zero enrollments ever.

## Sales Hub audit checklist: pipelines, deals, ownership, follow-up

A HubSpot sales audit asks one question: can anyone trust what the pipeline says? Count open deals with no amount, no close date or a close date already past. Count deals with no activity in 60 days, deals owned by people who left, sales-stage contacts nobody owns, and overdue tasks. Each one makes the forecast wrong before anyone applies judgment.

| Area                   | Check                                                                                                                | Graded on                                          |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Pipeline configuration | Pipelines with zero deals; pipelines with more than 10 open stages                                                   | Empty + bloated pipelines, as a share of pipelines |
| Deal data quality      | Open deals missing amount, close date, owner, or any associated contact; closed-lost deals with no loss reason       | Missing amount + missing close date                |
| Pipeline hygiene       | Open deals with no logged activity in 60+ days; open deals with a past close date; open deals with no next activity  | Stale + past-due deals                             |
| Ownership and handoff  | Open deals owned by deactivated users; SQL and Opportunity contacts with no owner; Opportunity contacts with no deal | Orphaned deals + unowned sales-stage contacts      |
| Activity and follow-up | Open tasks; overdue open tasks; leads with no owner                                                                  | Overdue tasks, as a share of open tasks            |

"Open" means `hs_is_closed` = false. That filter works across every pipeline, whatever the stages are called.

Set the 60-day stale window to your sales cycle before reading the grade. Sixty days is strict for enterprise deals and generous for transactional ones.

What I fix first:

1. **Orphaned open deals.** Nobody follows up, and they appear in nobody's forecast.
2. **Past-due close dates.** The deal closed, slipped or died, and the record says none of those.
3. **Stale deals, after sampling.** No activity can mean a dead deal or a rep who does not log. Check ten before deciding.

The 90-day win rate is worth noting for context but should not drive a grade. A healthy win rate on a pipeline full of stale deals usually means losses are never closed out. More on this in [nobody trusts the forecast](/problems/hubspot-pipeline-forecast-not-trusted).

Three UI settings prevent most of these findings: required properties per deal stage (Settings > Objects > Deals > Pipelines), pipeline rules that stop stage skipping, and a workflow that creates a task when a deal goes stale.

## Properties and integrations: the checks most audits skip

Most audits stop at contacts and deals. Two more areas break things quietly. Custom properties nobody uses clutter forms and mapping. Integrations still calling old API versions will stop getting fixes. HubSpot's v4 APIs lose support on March 30, 2027, and v1-v3 have been unsupported since September 15, 2026, with enforcement in September 2027.

### Properties

- Custom properties with zero populated records and no use in any form, workflow or list.
- Names containing "test", "temp", "old\_" or "copy_of".
- Properties created by integrations you have switched off.
- Leave Salesforce sync properties alone until the Salesforce admin agrees.

Archive first, wait 30 days, then delete. [Cleanup properties](/skills/cleanup-properties) does the inventory.

### Integrations and API versions

1. Open Settings > Integrations > Private Apps and Service Keys. In each legacy private app, open **Logs**. The request paths show the version (`/crm/v3/...`, `/contacts/v1/...`).
2. List every app under Settings > Integrations > Connected Apps, and ask vendors of business-critical ones about their migration.
3. Search your own code for `/v1/`, `/v2/` and `/v3/` HubSpot paths.
4. Check custom HTTP steps in Zapier, Make or similar. Their managed connectors migrate on the vendor's schedule; your custom steps do not.

Mark each caller red (v1/v2), amber (v3, v4, or a legacy private app) or green (date-based paths with a service key). Legacy private apps must move to service keys by September 2027. The [2027 API deadline page](/problems/hubspot-api-versions-2027-deadline) and [audit API usage](/skills/audit-api-usage) skill cover this end to end.

## HubSpot audit template: copy this

Paste this into a doc or spreadsheet. Fill in the count and total, divide, and grade with the table above.

```text
HUBSPOT PORTAL AUDIT    Date: ____    Portal: ____    Auditor: ____

SHARED                                   Count   Total   %    Grade
Contacts with no owner                   ____    ____    __
Contacts owned by deactivated users      ____    ____    __   ___ (with row above)
Companies missing domain                 ____    ____    __   ___

MARKETING
Hard bounced                             ____    ____    __
Globally unsubscribed                    ____    ____    __   ___ (with row above)
Contacts missing email                   ____    ____    __
Contacts missing lifecycle stage         ____    ____    __   ___
Never opened any email                   ____    ____    __   ___
Customers not at Customer stage          ____    ____    __
Lists / workflows (inactive) / forms     ____ / ____ (____) / ____

SALES
Pipelines empty or >10 open stages       ____    ____    __   ___
Open deals missing amount                ____    ____    __
Open deals missing close date            ____    ____    __   ___ (with row above)
Open deals stale 60+ days                ____    ____    __
Open deals with past close date          ____    ____    __   ___ (with row above)
Open deals owned by deactivated users    ____    ____    __
SQL/Opportunity contacts with no owner   ____    ____    __   ___ (with row above)
Overdue open tasks                       ____    ____    __   ___

INTEGRATIONS
Callers on v1/v2 (red)                   ____
Callers on v3/v4 or legacy private apps  ____
Unused custom properties                 ____

TOP 3 FIXES:
1. ________   2. ________   3. ________
```

## How do you run a HubSpot audit with a script instead?

The `/hubspot-audit` skill runs every check above as read-only API queries and writes a graded Markdown report with a JSON copy. It opens with a prescription: each finding mapped to the skill that fixes it, ordered P0 first, then by record count. It typically runs in minutes, even on six-figure databases.

Three commands, from Claude Code:

```text
/plugin marketplace add tomgranot/hubspot-admin-skills
/plugin install hubspot-admin@hubspot-admin-skills
/hubspot-audit
```

You need a HubSpot service key with read scopes, Python 3.10+ and `uv`. Own only one side of the portal? Run [`/hubspot-marketing-audit`](/skills/hubspot-marketing-audit) or [`/hubspot-sales-audit`](/skills/hubspot-sales-audit). Both use the same engine, so shared numbers match.

When the report is done, [`/hubspot-implementation-plan`](/guides/hubspot-implementation-plan-template) turns it into a phased plan. To keep the portal clean afterwards, see the [HubSpot admin checklist](/guides/hubspot-admin-checklist).

## FAQ

### Is a HubSpot audit free?

Doing it by hand costs your time. The skills here are free and open source under the MIT license. You need Claude Code and a HubSpot service key. No Marketing Hub or Sales Hub tier is required for the audit itself; rows that need a hub you don't have show `n/a`.

### Is it safe to run on a production portal?

Yes. The audit only searches and counts. It writes nothing to HubSpot. Its output is a Markdown report and a JSON file in a local `reports/` folder on your machine. There is nothing to roll back. Delete the files if you want them gone.

### Will the audit change or break anything?

No. Changes only happen when you run a fix skill, and those export a CSV of every affected record first, show you what will change, ask before writing and stop at an abort threshold. To check that on a throwaway portal first, run [`/sandbox-self-test`](/skills/sandbox-self-test) against a free HubSpot developer test account.

### Do I need a developer?

No. You need someone who can create a service key under Settings > Integrations > Service Keys and paste it into a `.env` file. Claude Code runs the script and reads the report with you.

### What does "n/a" or "?" mean in the report?

The token could not read that object, usually because a scope is missing or the hub is not purchased. It does not mean the area is clean. Add the scope and re-run.

### What is this audit not for?

Content, SEO and website audits are out of scope, and so is campaign performance (per-email open and click rates, attribution). It does not assess whether your consent model is legally compliant, and it does not score individual reps.

### Is this the same as the HubSpot audit log?

No. The HubSpot audit log is HubSpot's own record of what users did in the account: logins, security changes and other activity. Super Admins find it in Settings under Account Management > Audit Logs. Some filter categories need an Enterprise subscription. This guide is about auditing your data, not user activity.

---

**Next step:** [install the skills](/install) and run `/hubspot-audit`. You will have a graded report and a fix list before your coffee goes cold.
