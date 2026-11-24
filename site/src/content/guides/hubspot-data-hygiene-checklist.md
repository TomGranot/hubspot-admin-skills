---
title: 'HubSpot Data Hygiene Checklist: What to Clean, in Order'
description: 'A HubSpot data hygiene checklist you can run by hand: no-email contacts, bounces, unsubscribes, duplicates, orphaned owners, dead lists. Plus a scripted path.'
heading: 'HubSpot data hygiene checklist'
updated: 2026-11-25
order: 3
skills:
  - delete-no-email-contacts
  - suppress-hard-bounced
  - merge-duplicate-companies
---

HubSpot data hygiene means finding the records that cost you money or lie in your reports, and fixing them in a safe order. Start with a read-only audit. Then delete contacts with no email, suppress hard bounces and unsubscribes, merge duplicate companies, and reassign records owned by people who left. Then schedule the checks so the mess does not return.

Every step below works by hand in the HubSpot UI. If you would rather have Claude Code run it with an audit trail, the open-source skills do the same checks as scripts. **[Install the skills](/install)** and skip the clicking.

## What is HubSpot data hygiene?

Data hygiene is the routine work of keeping CRM records usable: reachable contacts, one record per real company, a living owner on every record, and properties that mean the same thing everywhere.

In HubSpot it has a billing side as well. Marketing contacts count toward your tier whether or not you can email them. A messy HubSpot CRM pays for contacts it cannot reach and reports on numbers nobody trusts.

German-speaking admins call the leftover clutter _Altlasten_: the dead lists, test workflows and orphaned records a portal piles up over the years. The checklist below covers both the database and that clutter.

## Where should a HubSpot cleanup start?

Start by measuring, not deleting. A cleanup without a baseline can't show what it fixed, and it tends to start with whatever annoyed someone last week rather than whatever costs the most.

By hand: open **Data Management > Data Quality** and note what HubSpot flags. Then build a few filtered contact views (email is unknown, lifecycle stage is unknown, contact owner is unknown) and write down the counts.

Scripted: the `/hubspot-audit` skill runs read-only API queries across contacts, companies, deals and owners. It grades each dimension A to F by the share of records affected, and writes a report whose first table is the ordered list of fixes. It makes no writes.

## The HubSpot data hygiene checklist

Work top to bottom. The order matters: you don't want to enrich or score records you are about to delete.

| #   | Check                                    | How to find it in HubSpot                               | Fix                                   | Skill                           |
| --- | ---------------------------------------- | ------------------------------------------------------- | ------------------------------------- | ------------------------------- |
| 1   | Contacts with no email                   | Contacts filter: Email is unknown                       | Delete (recoverable for 90 days)      | `/delete-no-email-contacts`     |
| 2   | Hard-bounced contacts                    | Filter on hard bounce reason is known                   | Set as non-marketing                  | `/suppress-hard-bounced`        |
| 3   | Globally unsubscribed contacts           | Filter: unsubscribed from all email is true             | Set as non-marketing, never delete    | `/suppress-global-unsubscribes` |
| 4   | Ghost contacts (delivered, never opened) | Emails delivered is known, opens is unknown             | Suppress after review                 | `/suppress-ghost-contacts`      |
| 5   | Duplicate companies                      | Group by company domain                                 | Merge one reviewed pair at a time     | `/merge-duplicate-companies`    |
| 6   | Records owned by deactivated users       | Owners API with `archived=true`                         | Reassign to a successor               | `/reassign-deactivated-owners`  |
| 7   | Unused lists                             | Lists with zero members, test names, stale static lists | Archive, then delete                  | `/cleanup-lists`                |
| 8   | Dead workflows                           | Off for 90+ days, zero enrollments, test names          | Export, turn off, delete a week later | `/cleanup-workflows`            |

Items 1 to 6 are the [database hygiene category](/categories/database-hygiene). Items 7 and 8 are the clutter that makes the portal hard to read. Both are below in more detail.

### 1. Delete contacts with no email address

Contacts without an email can't receive marketing, sequences or transactional mail, and they still inflate the billed count. Before deleting, ask why they exist: an integration or form may be creating them on purpose. Fix that inflow first.

Deleted contacts are recoverable for 90 days under **Settings > Data Management > Deleted Objects**. The skill exports a CSV of every record first and aborts above 500 contacts unless you raise the threshold.

### 2. Suppress hard-bounced contacts

Every send to a hard-bounced address tells mailbox providers you don't clean your list. Find them with the hard bounce reason property (`hs_email_hard_bounce_reason_enum` in the API, with the `_enum` suffix).

To suppress by hand: open the list, tick the header checkbox, click **Select all**, then **More > Set marketing contact status > Set as non-marketing contact**. That last step can't be scripted. `hs_marketable_status` is read-only through the API, so the skill builds the active list and you click the button.

### 3. Suppress global unsubscribes, don't delete them

A globally unsubscribed contact can never be emailed again. If they are still a marketing contact, you are paying for the privilege. Filter on `hs_email_optout` being true and set them as non-marketing.

Don't delete them. The record is what keeps the opt-out on file. Delete it, re-import the person later, and you can email them again by accident. Never re-subscribe anyone in bulk, even if the unsubscribes look like an import error.

### 4. Review ghost contacts before suppressing

Ghosts have received your email and never opened one. HubSpot stores "never opened" as an empty property, not as zero. A filter for opens equal to 0 returns nothing. Use "is unknown" in the UI or `NOT_HAS_PROPERTY` in the API.

Apple Mail Privacy Protection records opens nobody made, so some real ghosts look engaged. Weigh clicks more than opens. Suppress the worst offenders first and watch the rest.

### 5. Merge duplicate companies, carefully

Duplicates split deals, contacts and activity across records, and every account report undercounts. Group companies by domain first; shared domains are near-certain duplicates. Name matches produce more false positives ("State University").

Company merges can't be undone. HubSpot keeps the primary record's value when both records have one. Check phone, address and industry before you confirm, and merge customers first. HubSpot's own duplicate tool lives under **Data Management > Data Quality > Manage Duplicates**.

### 6. Reassign records owned by people who left

Deactivating a user doesn't reassign their records. Routing, task alerts and owner-based reports keep pointing at an inbox nobody reads. Some HubSpot views hide deactivated users from the owner filter, so a clean-looking filter proves nothing.

The API only returns deactivated owners when you pass `archived=true`. Decide the successor for each departed user before you touch anything.

### 7. Clean up lists (list hygiene)

"List hygiene" means two things in HubSpot. One is the email side: items 2 to 4 above. The other is the list objects: zero-member lists, lists no workflow or email uses, "test" and "copy of" lists, static lists untouched for six months.

Check before deleting. A list with zero members can still be a workflow enrollment trigger. Prefix candidates with `[ARCHIVE]`, wait a quarter, then delete.

### 8. Retire dead workflows

Flag workflows that have been off for 90+ days, never enrolled anyone, or carry test names. Before deleting one, check whether another workflow depends on it or on a property it sets.

Deleted workflows can't be restored in HubSpot. Export the definitions first (`/workflows-as-code` writes each one to JSON), turn the workflow off, wait a week, then delete.

## Does HubSpot clean data automatically?

Partly. HubSpot's data quality tools (**Data Management > Data Quality**) flag duplicate contacts and companies, which you review and merge or reject. The overview and duplicate management come with Starter, Professional and Enterprise across Marketing, Sales, Service, Data and Content Hub.

The rest is tier-gated. Managing formatting issues in bulk needs Data Hub Starter or above. Automating formatting fixes, duplicate alerts and property anomaly detection need Data Hub Professional or Enterprise.

What the tools won't decide for you is policy: which contacts to stop paying for, who inherits a departed rep's accounts, which lists are dead. That is the checklist above.

## How do you keep HubSpot clean after the cleanup?

A cleanup gives you a clean moment, not a clean system. Put two routines on the calendar and add prevention at the point of entry.

- **Weekly, five minutes:** new bounces, contacts created this week (email, company, lifecycle stage present?), workflows in error, sudden list growth, a 10-contact sample. If more than 2 of 10 have gaps, dig deeper. (`/weekly-cleanup-routine`)
- **Quarterly:** re-run the audit, compare to last quarter, and flag any completeness metric that dropped more than five points. (`/quarterly-database-cleanup`)
- **Prevention:** a new-contact hygiene workflow and a bounce-monitoring workflow. The skills create both through HubSpot's Workflows API, switched off, so you review them before they run.

## The scripted path: same checklist, with a paper trail

Every skill that changes data follows the same four stages: **Plan, Before, Execute, After**.

1. **Plan:** the skill asks the questions above (root cause, thresholds, successor owners) before it writes code.
2. **Before:** read-only counts and a CSV export of every affected record.
3. **Execute:** a typed confirmation, then batch changes with an abort threshold.
4. **After:** the same query again, to prove the count went down.

Each skill also documents its rollback. The scripts are plain Python calling HubSpot's REST API with a service key, run with `uv`. Audit CSVs go to `data/audit-logs/`, which is gitignored because they may hold personal data.

Two commands in Claude Code:

```
/plugin marketplace add tomgranot/hubspot-admin-skills
/plugin install hubspot-admin@hubspot-admin-skills
```

Then run `/hubspot-audit` and work down the prescription it writes.

## FAQ

### What does it cost?

The skills are free and MIT-licensed. You need Claude Code and a HubSpot service key. The cleanup itself can lower your bill: contacts you set as non-marketing stop counting toward your marketing contact tier at the start of the next billing cycle, not immediately.

### Is it safe to run on a production portal?

The audit is read-only. Skills that write export a CSV first, ask for typed confirmation, and stop above a threshold. If you want proof before production, `/sandbox-self-test` runs the toolkit against a free HubSpot developer test account and refuses, in code, to run against anything else.

### Will this break our workflows or reports?

It can, if you skip the checks. Deleting a list can break a workflow that enrolls from it. Merging companies is permanent. That's why each skill makes you confirm dependencies and review candidates before it writes, and why the workflow cleanup tells you to export every definition first.

### Do I need a developer?

No. You need someone who can paste a service key into a `.env` file and answer Claude's questions about your business rules. Every manual step above works without code at all.

### Should I delete or suppress?

Suppress anything with history or consent value: bounces, unsubscribes, ghosts. Delete only records with no use, like contacts with no email. Suppression keeps the record and its opt-out; deletion is recoverable for only 90 days.

### What is this not for?

It doesn't replace your judgment on business rules, and it doesn't fill in missing data. For that, see the [HubSpot data enrichment guide](/guides/hubspot-data-enrichment). It also won't fix a broken integration that keeps creating bad records. Find and fix the source first.

**Ready to run it? [Install the HubSpot Admin Skills](/install)** and start with `/hubspot-audit`.
