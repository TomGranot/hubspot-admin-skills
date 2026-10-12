---
name: hubspot-audit
description: "Run a full, read-only HubSpot portal audit covering both the marketing and sales sides: database, deliverability, engagement, owners, pipelines, deal quality, and follow-up. Grades each dimension and prescribes the skills that fix what it finds. Use when starting a CRM cleanup, onboarding a new portal, or running a quarterly health check."
license: MIT
metadata:
  author: tomgranot
  version: "2.0"
  category: audit-planning
---

# HubSpot Portal Audit

Run a full diagnostic audit of a HubSpot portal. One read-only script collects the metrics, grades each dimension, and writes a report that opens with a prioritized list of skills to run.

## One Engine, Three Lenses

The audit is a single engine (`scripts/audit_portal.py`) with a `--scope` flag. Every dimension is tagged **shared**, **marketing**, or **sales**:

| Scope | Runs | Report | Entry point |
|-------|------|--------|-------------|
| `full` (default) | shared + marketing + sales | `reports/hubspot-audit-{date}.md` | this skill |
| `marketing` | shared + marketing | `reports/hubspot-marketing-audit-{date}.md` | `/hubspot-marketing-audit` |
| `sales` | shared + sales | `reports/hubspot-sales-audit-{date}.md` | `/hubspot-sales-audit` |

The shared dimensions run under every scope, so a marketing audit and a sales audit of the same portal agree on the numbers they have in common. Use this skill when you own the whole portal; hand a team the scoped audit when they only own one side.

## Setup

1. **Get the API token.** Check `.env` for `HUBSPOT_ACCESS_TOKEN`. If it is not set, ask the user for a read-scoped HubSpot access token and store it in `.env`:
   ```
   HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx
   ```

2. **Run the audit.** The script carries PEP 723 inline metadata and runs with [`uv`](https://github.com/astral-sh/uv), which resolves its dependencies automatically:
   ```bash
   uv run scripts/audit_portal.py              # full
   uv run scripts/audit_portal.py --scope marketing
   uv run scripts/audit_portal.py --scope sales
   ```

The script creates `reports/` if needed and writes a markdown report plus a JSON twin (same name, `.json`) for other skills to read.

## Audit Dimensions

### Shared (every scope)

| Dimension | What it measures | Graded on |
|-----------|------------------|-----------|
| Database Size | Total contacts, companies, deals | not graded |
| Owner Health | Unowned contacts and companies; records still owned by deactivated owners | unowned + orphaned contacts |
| Company Data Completeness | Companies missing domain, industry, country | missing domain |
| Duplicates | Flagged for `/merge-duplicate-companies` (exact scans need full pagination) | not graded |

### Marketing

| Dimension | What it measures | Graded on |
|-----------|------------------|-----------|
| Email Deliverability | Marketing contacts, hard bounces, global unsubscribes, 3+ bounces, never emailed | hard bounces + unsubscribes |
| Contact Data Completeness | Contacts missing email, lifecycle stage, company, industry, country, job title | missing lifecycle stage |
| Engagement Health | Opened in 90 days, never opened, last open over a year ago, current customers at the wrong lifecycle stage | never opened |
| List, Workflow & Form Health | Total lists, workflows (active vs inactive), forms | not graded |

### Sales

| Dimension | What it measures | Graded on |
|-----------|------------------|-----------|
| Pipeline Configuration | Pipelines, deals per pipeline, empty pipelines, pipelines with more than 10 open stages | empty + bloated pipelines |
| Deal Data Quality | Open deals missing amount, close date, owner, or an associated contact; closed-lost deals with no loss reason | missing amount + close date |
| Pipeline Hygiene & Velocity | Open deals with no activity in 60+ days, close dates in the past, no next activity; 90-day win rate | stale + past-due deals |
| Sales Ownership & Handoff | Open deals owned by deactivated owners; SQL/Opportunity contacts with no owner; Opportunity contacts with no deal | orphaned deals + unowned sales-stage contacts |
| Activity & Follow-up | Open and overdue tasks; leads and unowned leads | overdue tasks |

Thresholds (stale-deal window, win-rate window, stage limit) are in the `# --- Configuration ---` block at the top of the script.

## API Technical Notes

- **Null checks**: use the `NOT_HAS_PROPERTY` operator to find records where a property has never been set. HubSpot stores "never happened" as an absent property, not as 0 or an empty string.
- **Counting**: the script counts with the Search API's `total`, which is exact even past the 10,000-result paging cap. Paging through more than 10,000 *records* requires segmenting the query.
- **Search limits**: 5 requests per second, 5 filter groups per query, 6 filters per group. The script paces itself under the rate limit.
- **n/a is not zero**: when the token cannot read an object (missing scope, or the hub is not purchased), the row shows `n/a` and the dimension grades `?`. Fix the scope and re-run rather than reading it as clean.
- **Deactivated owners**: the Owners API only returns them with `archived=true`.
- **Open deals**: filtered with `hs_is_closed = false`, which works across every pipeline regardless of stage names.
- **Marketing contact status**: `hs_marketable_status` is readable and filterable but **read-only via API**.
- **Not available by API**: per-email open/click rates come from the marketing email statistics API or the UI; forecast accuracy and time-in-stage come from the UI's forecast and pipeline reports.

## Scripts

Script paths are relative to this skill's directory. Run them from your project directory so `.env`, `data/`, and `reports/` resolve there: prefix each path with wherever this skill is installed (`skills/hubspot-audit/` in a clone of the repo).

| Stage | Script | Run with |
|-------|--------|----------|
| Audit (read-only) | [`scripts/audit_portal.py`](./scripts/audit_portal.py) | `uv run scripts/audit_portal.py [--scope full\|marketing\|sales]` |

If a portal needs a check the script does not cover, add a dimension function with the right tag rather than writing a separate one-off script. The offline tests in `tests/test_audit_portal.py` run against a fake API and need no portal.

**MCP note:** if HubSpot's MCP server is connected (see `/connect-hubspot-mcp`), use it for spot-checks while auditing: opening sample records behind a suspicious count is faster than writing one-off queries. The counting queries themselves stay in the script for reproducibility.

## Grading Rubric

| Grade | Meaning | Criteria |
|-------|---------|----------|
| A | Healthy | < 5% of records affected |
| B | Minor issues | 5-15% of records affected |
| C | Needs attention | 15-30% of records affected |
| D | Significant problems | 30-50% of records affected |
| F | Critical | > 50% of records affected |
| ? | Unknown | The metric could not be read |

The script grades each dimension on the metric named in the tables above. Treat the grade as a starting point: a portal with 40 open deals and 3 stale ones is in a different place than one with 4,000 and 300, even though both grade B.

## Report Structure

```markdown
# HubSpot CRM Audit Report

**Date:** YYYY-MM-DD
**Scope:** full

## Executive Summary

| Dimension | Lens | Grade |
|---|---|---|
| Owner Health | shared | C |
| Email Deliverability | marketing | D |
| Deal Data Quality | sales | B |

## Prescription

| # | Skill | Why | Records | Priority |
|---|---|---|---|---|
| 1 | `/delete-no-email-contacts` | Contacts missing email | X,XXX | P0 |
| 2 | `/suppress-hard-bounced` | Hard bounced | X,XXX | P0 |

## 1. Database Size
...one section per dimension, each a Metric | Count | % table...
```

## Skill Prescription

The script builds the prescription itself: every metric with a non-zero count that maps to a fix skill becomes a row, each skill appears once, and rows are ordered by priority (P0 first), then by record count.

After the script finishes:

### Step 1: Read the Report

Read the generated markdown report. Do not re-derive counts by hand; the report and its JSON twin are the source of truth.

### Step 2: Present the Ordered Prescription

Present the prescription as a numbered action list grouped by urgency, with the real counts:

```markdown
## Your Cleanup Prescription

### Immediate (P0)
1. `/delete-no-email-contacts`: X,XXX contacts with no email are inflating your bill
2. `/reassign-deactivated-owners`: XX open deals belong to people who have left

### Next (P1)
3. `/cleanup-deals`: XXX open deals have no amount or close date
...
```

Add judgment the script cannot: which findings share a root cause, which are expected for this business, and what order respects dependencies (enrichment before scoring, ownership before routing).

### Step 3: Handle Missing Skills

If the audit reveals a problem that **no existing skill covers**, do the following:

1. **Tell the user clearly**: "This audit found an issue that isn't covered by any existing skill: [description]."
2. **Offer to create it on the spot**: "I can create a new skill for this right now. It would be called `/[suggested-name]` and would handle [brief description]."
3. **Ask about contributing upstream**: "Would you like to contribute this new skill back to the community? If yes, I'll:
   - Create the skill in `skills/[name]/SKILL.md`
   - Fork the repo (if not already forked)
   - Push the new skill to your fork
   - Open a pull request to `tomgranot/hubspot-admin-skills`

   This helps everyone who uses these skills in the future."
4. If the user agrees, create the skill following the standard SKILL.md format, commit it, and open the PR.
5. If the user declines the upstream contribution, still create the skill locally so they can use it.

### Step 4: Suggest Next Step

End with:
```
Ready to start? Run `/hubspot-implementation-plan` to generate a full phased plan,
or jump straight to the first skill in your prescription.
```

## After Running

- Print the file path of the saved report
- Present the ordered skill prescription (Step 2 above)
- Highlight the top 3 most critical findings
- Flag any findings that have no matching skill (Step 3 above)
- Suggest running `/hubspot-implementation-plan` for the full phased plan
