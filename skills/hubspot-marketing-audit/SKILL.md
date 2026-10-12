---
name: hubspot-marketing-audit
description: "Audit the marketing side of a HubSpot portal: email deliverability, contact data completeness, engagement, lifecycle consistency, and list, workflow, and form sprawl. Read-only. Use when marketing ops owns the cleanup, before a re-engagement or migration project, or when the marketing contact bill keeps climbing."
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: audit-planning
---

# HubSpot Marketing Audit

A read-only audit of everything marketing operations owns in a HubSpot portal. It answers three questions: can we reach the people in this database, do we know enough about them to segment, and how much of what we pay for is dead weight.

## Why This Matters

Marketing pays for contacts by the tier and earns deliverability by the send. A database full of bounced, unsubscribed, and never-engaged contacts costs money on one side and sender reputation on the other, and both problems stay invisible until someone counts. This audit counts.

## How It Relates to the Other Audits

This skill is a lens on the same engine that powers `/hubspot-audit` and `/hubspot-sales-audit`. It runs the **shared** dimensions (database size, owner health, company data, duplicates) plus the **marketing** dimensions, and skips pipelines and deals entirely. Because the shared dimensions are computed by the same code under every scope, the numbers here match what the sales team sees in their audit.

| If you own | Run |
|------------|-----|
| Marketing only | this skill |
| Sales only | `/hubspot-sales-audit` |
| The whole portal | `/hubspot-audit` (both lenses in one report) |

## Prerequisites

- The `hubspot-audit` skill installed alongside this one (it ships the engine)
- `HUBSPOT_ACCESS_TOKEN` in `.env`, with read scopes for contacts, companies, owners, lists, forms, and `automation`
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)

No Marketing Hub tier is required to run the audit. Rows that need a feature the portal does not have show `n/a`.

## Run It

The engine lives in the `hubspot-audit` skill, one directory over from this one. Run it from your project directory so `.env` and `reports/` resolve there (in a clone of the repo the path is `skills/hubspot-audit/scripts/audit_portal.py`).

```bash
uv run ../hubspot-audit/scripts/audit_portal.py --scope marketing
```

Output: `reports/hubspot-marketing-audit-{YYYY-MM-DD}.md` and a `.json` twin.

## What It Measures

| Dimension | Metrics | Graded on |
|-----------|---------|-----------|
| Email Deliverability | Marketing contacts, hard bounces, global unsubscribes, 3+ bounces, never emailed | hard bounces + unsubscribes |
| Contact Data Completeness | Missing email, lifecycle stage, company, industry, country, job title | missing lifecycle stage |
| Engagement Health | Opened in 90 days, never opened, last open over a year ago, current customers at the wrong stage | never opened |
| List, Workflow & Form Health | Total lists, active vs inactive workflows, forms | not graded |
| *Shared:* Owner Health, Company Data, Database Size, Duplicates | see `/hubspot-audit` | |

## Reading the Results

The script produces counts and a prescription. The interpretation is the part that needs a person, or Claude with context:

1. **Start with what is billed but unreachable.** Hard-bounced and globally unsubscribed contacts that are still marketing contacts are pure cost. These are P0 for a reason: the fix is safe, fast, and pays for itself.
2. **Separate "never emailed" from "never opened".** Never emailed is often fine (sales-owned contacts, recent imports). Never opened after many sends is a ghost contact and a deliverability liability.
3. **Check Apple Mail Privacy Protection before trusting opens.** Machine opens inflate open-based engagement. If the "opened in 90 days" share looks too healthy, use clicks as the engagement signal when deciding who to sunset.
4. **Read completeness against how you segment.** A missing job title only matters if you segment or score on it. Ask which properties drive lists, scoring, and routing, and weigh those gaps first.
5. **Treat asset counts as a prompt, not a verdict.** The audit reports how many lists, workflows, and forms exist. Whether 300 lists is sprawl depends on the team; the cleanup skills do the per-asset analysis.

## From Findings to Fixes

The report's Prescription table maps each finding to its skill. The usual marketing order:

| Order | Skill | Fixes |
|-------|-------|-------|
| 1 | `/delete-no-email-contacts` | Contacts that can never be emailed |
| 2 | `/suppress-hard-bounced`, `/suppress-global-unsubscribes` | Billed contacts you cannot or must not email |
| 3 | `/suppress-ghost-contacts` | Never-engaged contacts dragging down reputation |
| 4 | `/fix-lifecycle-stages`, `/enrich-company-name`, `/enrich-industry`, `/backfill-geo-data` | Gaps that block segmentation |
| 5 | `/create-icp-tiers`, `/build-lead-scoring`, `/build-smart-lists` | Targeting, once the data supports it |
| 6 | `/bounce-monitoring-workflow`, `/engagement-suppression-workflow`, `/new-contact-hygiene-workflow` | Keeping it fixed |
| 7 | `/cleanup-lists`, `/cleanup-forms`, `/cleanup-workflows` | Asset sprawl |

Run `/hubspot-implementation-plan` to turn the report into a phased plan with dependencies and effort estimates.

## What This Audit Does Not Cover

- **Campaign and channel performance.** Per-email open and click rates, attribution, and ad spend live in the marketing email statistics API and HubSpot's reports. This audit is about the database those campaigns run on.
- **Content and SEO.** Pages, blogs, and CTAs are out of scope.
- **Consent and legal basis.** The audit counts unsubscribes; it does not assess whether your consent model is compliant.

## Rollback

Nothing to roll back: the audit only reads. To remove its output, delete the files it wrote under `reports/`.
