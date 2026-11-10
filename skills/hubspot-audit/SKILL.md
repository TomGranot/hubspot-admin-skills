---
name: hubspot-audit
description: "Run a full, read-only HubSpot portal audit covering the marketing and sales sides: database, duplicates, deliverability, completeness, engagement, owners, pipelines, deal quality, and follow-up. Every finding carries sample records, a breakdown, root causes, the fix, and the prevention. Use when starting a CRM cleanup, onboarding a new portal, or running a quarterly health check."
license: MIT
metadata:
  author: tomgranot
  version: "3.0"
  category: audit-planning
---

# HubSpot Portal Audit

Run a full diagnostic audit of a HubSpot portal. One read-only script runs about 60 checks, grades each section on its worst finding, and writes a report where every finding shows the records behind it, where they came from, what fixes them, and what stops them recurring.

## One Engine, Selectable Lenses

The audit is a single engine (`scripts/audit.py`, built on the shared library in `lib/hubspot_admin/`) with a `--scope` flag. Every check belongs to a lens: **shared**, **marketing**, or **sales** (service, platform, and commerce lenses are planned).

| Scope | Runs | Report | Entry point |
|-------|------|--------|-------------|
| `full` (default) | shared + marketing + sales | `reports/hubspot-audit-{date}.md` | this skill |
| `marketing` | shared + marketing | `reports/hubspot-marketing-audit-{date}.md` | `/hubspot-marketing-audit` |
| `sales` | shared + sales | `reports/hubspot-sales-audit-{date}.md` | `/hubspot-sales-audit` |
| `marketing,sales` or any list | the union, in that order | `reports/hubspot-audit-{lenses}-{date}.md` | this skill |

The shared checks run under every scope, so a marketing audit and a sales audit of the same portal agree on the numbers they have in common.

## Setup

1. **Get the token.** Check `.env` for `HUBSPOT_ACCESS_TOKEN`. If it is not set, ask the user for a HubSpot service key (Settings > Integrations > Service Keys; an existing legacy private app token also works) with read scopes for contacts, companies, deals, owners, lists, forms, automation, and, if the portal has them, tasks and leads. Store it in `.env`:
   ```
   HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx
   ```

2. **Run the audit.** The script carries PEP 723 inline metadata and runs with [`uv`](https://github.com/astral-sh/uv):
   ```bash
   uv run scripts/audit.py                      # full
   uv run scripts/audit.py --scope marketing
   uv run scripts/audit.py --scope sales
   uv run scripts/audit.py --no-scan            # skip record scans (fast, but duplicates report as skipped)
   uv run scripts/audit.py --scan-cap 50000     # scan at most this many records per object
   uv run scripts/audit.py --stale-days 90      # stale-deal window (default 60)
   ```

   The script writes `reports/<name>-<date>.md`, a `.json` twin (`schema_version: 3`) for `/hubspot-implementation-plan`, and `reports/history/` for the next run's "since last time" diff. Record scans are cached under `data/cache/` for 12 hours (`--cache-ttl 0` forces a rescan). Both directories may contain PII and are gitignored.

3. **Expect it to take a while on a large portal.** Counts are one Search call each and pace themselves under the Search API's 5 requests per second. A full record scan of contacts and companies (needed to count duplicates and validate values) fetches 200 records per call, so a 250,000-contact portal is roughly 20 minutes. Use `--scan-cap` for a first look; the report labels any capped finding as partial.

## What It Checks

### Shared (every scope)

| Section | Checks | Needs |
|---------|--------|-------|
| Database Size & Growth | Totals; contacts created in the last 90 days by record source | — |
| Owner Health | Unowned contacts and companies; contacts owned by deactivated users (per user); owner load imbalance against an even split | owners scope |
| Company Data Completeness | Companies missing domain, industry, country, each by record source | — |
| Duplicates | Contacts by normalized email (case, plus-addressing, gmail dots), by phone, by name + company; companies by normalized domain (www, scheme, path) and by normalized name within a country. Counted from a record scan, with the biggest groups as evidence | record scan |
| Value Validity | Contacts whose email is not a valid address; free-mail share (context); contacts with no company whose email domain matches an existing company | record scan |

### Marketing

| Section | Checks |
|---------|--------|
| Email Deliverability | Marketing contacts; hard bounces; globally unsubscribed contacts still marketable; 3+ bounces; marketing contacts never emailed |
| Contact Data Completeness | Missing email, lifecycle stage, company, industry, country, job title, owner, first name. **One graded check per property**, so one healthy field cannot hide five empty ones |
| Engagement Health | Opened in 90 days; marketing contacts never opened after a send; last open over a year old; current customers not at the Customer stage |
| Lifecycle Funnel | Contacts per stage; Opportunity-stage contacts with no deal |
| List, Workflow & Form Health | Lists; workflows turned off (with test-named ones called out); forms |

### Sales

| Section | Checks |
|---------|--------|
| Pipeline Configuration | Pipelines and deals per pipeline; empty pipelines; pipelines with more than 10 open stages |
| Deal Data Quality | Open deals missing amount, close date, owner, or a contact; closed-lost deals with no loss reason; amounts over 10x the pipeline median |
| Pipeline Hygiene & Velocity | No activity in N+ days (per owner); close date in the past (per owner); no next activity; 90-day win rate |
| Sales Ownership & Handoff | Open deals owned by deactivated users; SQL/Opportunity contacts with no owner |
| Activity & Follow-up | Overdue open tasks (per owner); leads with no owner |

## How a Finding Is Reported

Every finding that has a count carries:

- **Count, denominator, share, severity** (ok, low, medium, high, critical)
- **Evidence**: up to 5 sample records with the properties that triggered the finding, deep-linked into the portal
- **Breakdown**: by record source, owner, pipeline, or lifecycle stage, whichever explains the finding
- **Why this happens**: a root cause the check tested, stated only when one breakdown value explains at least 40% of the finding
- **Fix**: the skill to run, or UI steps when no skill applies yet
- **Prevention**: the setting, validation rule, or workflow that stops it recurring

## Grading

| Grade | Meaning |
|-------|---------|
| A | Every check in the section ran and none reached low severity |
| B | Worst finding is low, **or** a check was skipped (an unread problem is not an absent one) |
| C | Worst finding is medium |
| D | Worst finding is high |
| F | Worst finding is critical |
| ? | Nothing in the section could be read |

Severity bands on the weighted share of affected records (<1% ok, <5% low, <15% medium, <30% high, otherwise critical), with two caps: fewer than 3 records is never above low, fewer than 10 never above medium, fewer than 50 never above high; and checks weighted under 1 (nice-to-have fields) never go critical. Each check's weight and thresholds are in `lib/hubspot_admin/checks/`.

A section grades on its **worst** finding. This is deliberate: in 2.0, Contact Data Completeness graded on lifecycle stage alone, and a portal missing company on 60% of contacts got an A.

## Coverage

The report ends with **What this audit could not check**: every skipped check, why (token lacks the scope, the portal lacks the hub, HubSpot exposes it only in the UI, a flag turned it off, the check failed), and how to get it. `n/a` is never reported as 0.

## API Technical Notes

- **Paths**: CRM object reads and searches use the date-based version `2026-09`. Owners, pipelines, lists, flows (beta), and forms still use their pre-2026 paths until re-verified; `lib/hubspot_admin/paths.py` is the single place they are defined.
- **Null checks**: `NOT_HAS_PROPERTY` finds records where a property was never set. HubSpot stores "never happened" as an absent property, not as 0 or an empty string.
- **Counting**: Search API `total` is exact past the 10,000-result paging cap. Scans get past the cap by splitting on `createdate` ranges until each piece fits.
- **Breakdowns**: the Search API has no group-by, so a breakdown is one count per known value (record sources, lifecycle stages, pipelines, the first 12 owners).
- **Not available by API**: workflow enrollment counts and error state, per-email open and click rates (marketing email statistics API, separate), forecast accuracy, time in stage, the UI's duplicate candidates list.
- **Marketing contact status**: `hs_marketable_status` is readable and filterable but read-only via API.

## Scripts

Script paths are relative to this skill's directory. Run them from your project directory so `.env`, `data/`, and `reports/` resolve there: prefix each path with wherever this skill is installed (`skills/hubspot-audit/` in a clone of the repo).

| Stage | Script | Run with |
|-------|--------|----------|
| Audit (read-only) | [`scripts/audit.py`](./scripts/audit.py) | `uv run scripts/audit.py [--scope full\|marketing\|sales\|a,b] [--no-scan] [--scan-cap N] [--stale-days N]` |
| Compatibility | `scripts/audit_portal.py` | forwards to `audit.py`; update old instructions |

To add a check, write a function under `lib/hubspot_admin/checks/` with the `@check` decorator (see CONTRIBUTING.md). The offline tests in `tests/test_audit_engine.py` run every check against a synthetic portal with planted defects; a new check should plant its defect there.

**MCP note:** if HubSpot's MCP server is connected (see `/connect-hubspot-mcp`), use it to open the evidence records behind a suspicious finding. The counting stays in the script for reproducibility.

## After the Script Finishes

### Step 1: Read the report, not the counts

The markdown and JSON are the source of truth. Do not re-derive counts by hand.

### Step 2: Present the prescription with judgment

The script orders the prescription by severity. Add what it cannot know:

- **Dependencies**: enrichment before scoring, ownership before routing, duplicates before anything that writes per record.
- **Shared root causes**: if three findings break down to the same import or integration, the fix is at the source, and the report's "why this happens" lines will say so.
- **What is expected for this business**: a 70% free-mail share is normal for B2C and a problem for B2B. Low activity logging may be a culture problem, not a data problem.
- **Materiality**: a portal with 40 open deals and 3 stale ones is in a different place than one with 4,000 and 300.

Present it as a numbered action list grouped by severity, with the real counts, then the "since last run" line when there is one.

### Step 3: Handle missing coverage

Read the "could not check" table. If a check was skipped for a missing scope, say which scope to add and offer to re-run. If the portal lacks the hub, say so once and move on.

### Step 4: Handle findings with no skill

Some findings name UI steps instead of a skill (duplicate contacts, companies missing domain). Walk the user through the steps, or offer to script the one-off with the shared library. If the fix is reusable, it is a candidate skill: create it under `skills/` following CONTRIBUTING.md and offer to open a PR.

### Step 5: Suggest the next step

```
Ready to start? Run `/hubspot-implementation-plan` to generate a phased plan,
or jump straight to the first skill in your prescription.
```

## Rollback

Nothing to roll back: the audit only reads. To remove its output, delete `reports/` and `data/cache/`.
