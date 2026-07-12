---
name: hubspot-audit
description: "Run a comprehensive HubSpot CRM database audit. Analyzes contacts, companies, deals, engagement, data quality, and deliverability. Use when starting a CRM cleanup, onboarding a new client, or performing quarterly health checks."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: audit-planning
---

# HubSpot CRM Database Audit

Run a full diagnostic audit of a HubSpot CRM portal. This skill collects metrics across eight dimensions, grades each one, and produces a prioritized report with actionable recommendations.

## Setup

1. **Get the API token.** Check `.env` for `HUBSPOT_ACCESS_TOKEN`. If it is not set, ask the user to provide their HubSpot private app access token and store it in `.env`:
   ```
   HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx
   ```

2. **No package install needed.** Scripts carry PEP 723 inline metadata and run with [`uv`](https://github.com/astral-sh/uv), which resolves `requests` and `python-dotenv` automatically:
   ```bash
   uv run skills/hubspot-audit/scripts/audit_portal.py
   ```

3. **Create the output directory** if it does not exist:
   ```bash
   mkdir -p reports
   ```

## Audit Dimensions

Run queries for each of the following eight dimensions. Collect exact counts for every metric listed.

### 1. Database Size
- Total contacts
- Total companies
- Total deals
- Marketing contacts vs non-marketing contacts (if Marketing Hub is active)

### 2. Email Deliverability
- Hard bounced contacts (`hs_email_hard_bounce_reason_enum` is not empty)
- Soft bounced contacts (`hs_email_bounce` > 0 AND no hard bounce)
- Global unsubscribes (`hs_is_unworked` or `hs_email_optout` = true)
- Never-emailed contacts (no `hs_email_last_send_date`)
- Invalid email format (regex check on `email` property)
- Contacts with 3+ bounces

### 3. Data Completeness
- Missing `email`
- Missing `company` (contact-level)
- Missing `industry` (contact-level)
- Missing `country` and/or `state`
- Missing `lifecyclestage`
- Missing `hubspot_owner_id`
- Missing `jobtitle`
- Companies missing `domain`
- Companies missing `industry`
- Companies missing `city` / `state` / `country`

### 4. Engagement Health
- Last activity distribution: active in last 30 days, 31-90 days, 91-180 days, 181-365 days, 365+ days, never engaged
- Contacts who opened an email in the last 90 days (`hs_email_last_open_date`)
- Contacts who never opened any email
- Contacts with zero page views
- Contacts with zero form submissions
- Current-customer consistency: contacts where `hs_current_customer` = true but lifecycle stage is not Customer (the `hs_current_customer` system property is read-only, set by HubSpot, and available since June 2026)

Note: aggregate *per-email* open/click rates are not derivable from contact properties — they come from the marketing email statistics API (v3, Marketing Hub plans) or the email health dashboard in the UI. The per-contact last-open/last-click properties above are the right audit signal at the database level.

### 5. Duplicate Analysis
- Duplicate email addresses (exact match)
- Companies sharing the same `domain`
- Companies with very similar names (fuzzy — note: API cannot do fuzzy matching natively; count exact duplicates on `name` and flag for manual review)

### 6. Owner Health
- Deactivated owners who still have assigned contacts
- Deactivated owners who still have assigned companies
- Deactivated owners who still have assigned deals
- Contacts with no owner
- Companies with no owner

### 7. List & Workflow Health
- Total active lists vs static lists
- Lists with zero members
- Workflows currently active
- Workflows that have not enrolled anyone in 90+ days
- Forms with zero submissions
- Forms with submissions in last 30 days

### 8. Deal Pipeline Health
- Deals without `amount`
- Deals without `closedate`
- Deals in each pipeline stage
- Stale deals (no activity in 60+ days, still open)
- Average deal age by stage

## API Technical Notes

These details are critical for getting accurate results:

- **Null checks**: Use the `NOT_HAS_PROPERTY` filter operator to find contacts where a property has never been set. HubSpot stores "never happened" as null (property absent), not as 0 or empty string.
  ```python
  {
      "filterGroups": [{
          "filters": [{
              "propertyName": "hs_email_last_send_date",
              "operator": "NOT_HAS_PROPERTY"
          }]
      }]
  }
  ```

- **Search API pagination limit**: The Search API returns a maximum of 10,000 results per query. If you expect more than 10K, segment queries by another property (e.g., `createdate` ranges, lifecycle stage, or first letter of email) and sum the results.

- **Deactivated owners**: The Owners API does not return deactivated owners by default. Pass `archived=true`:
  ```python
  resp = requests.get(f"{BASE}/crm/v3/owners", headers=HEADERS,
                      params={"limit": 100, "archived": "true"})
  ```

- **Rate limiting**: Private apps are limited to 100 requests per 10 seconds. Add a small delay between batch calls or use exponential backoff on 429 responses.

- **Engagement timestamps**: Use `hs_last_sales_activity_timestamp` and `notes_last_contacted` for activity dating. `hs_email_last_open_date` and `hs_email_last_click_date` are useful for email engagement specifically.

- **Marketing contact status**: The property `hs_marketable_status` indicates whether a contact is set as a marketing contact. This property is **read-only via API**.

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Audit (read-only) | [`scripts/audit_portal.py`](./scripts/audit_portal.py) | `uv run skills/hubspot-audit/scripts/audit_portal.py` |

## Script Structure

This skill ships [`scripts/audit_portal.py`](./scripts/audit_portal.py), which:

1. Loads `HUBSPOT_ACCESS_TOKEN` from `.env`
2. Calls the REST endpoints directly with `requests`:
   ```python
   TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
   BASE = "https://api.hubapi.com"
   HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
   ```
3. Runs each dimension's queries sequentially (respecting rate limits)
4. Collects all results into a structured dict
5. Computes letter grades per dimension (see grading rubric below)
6. Renders the markdown report
7. Saves to `reports/hubspot-audit-{YYYY-MM-DD}.md`

If a dimension needs portal-specific queries beyond what the script covers, extend it with the same house style rather than writing a separate one-off script.

**MCP note:** if HubSpot's MCP server is connected (see `/connect-hubspot-mcp`), use it for spot-checks while auditing — opening sample records behind a suspicious count is faster than writing one-off queries. The audit's counting queries themselves should stay in the script for reproducibility.

## Grading Rubric

Assign a letter grade to each dimension based on severity:

| Grade | Meaning | Criteria |
|-------|---------|----------|
| A | Healthy | < 5% of records affected |
| B | Minor issues | 5-15% of records affected |
| C | Needs attention | 15-30% of records affected |
| D | Significant problems | 30-50% of records affected |
| F | Critical | > 50% of records affected |

For dimensions without a simple percentage (e.g., Owner Health), use judgment based on the number of affected records and business impact.

## Output Format

Save the report to `reports/hubspot-audit-{YYYY-MM-DD}.md` with this structure:

```markdown
# HubSpot CRM Audit Report

**Date:** YYYY-MM-DD
**Portal ID:** [portal-id]

## Executive Summary

| Dimension | Grade | Key Finding |
|-----------|-------|-------------|
| Database Size | B | ~XX,000 contacts, XX,000 companies |
| Email Deliverability | D | XX% hard bounced, XX% globally unsubscribed |
| Data Completeness | F | XX% missing email, XX% missing industry |
| Engagement Health | D | XX% never engaged, XX% inactive 12+ months |
| Duplicate Analysis | C | ~X,XXX duplicate company domains |
| Owner Health | F | X deactivated owners with XX,XXX assigned contacts |
| List & Workflow Health | B | XX unused lists, X stale workflows |
| Deal Pipeline Health | C | XX% deals missing amount, XX stale deals |

**Overall Grade: X**

## Priority Recommendations

1. **[CRITICAL] Delete contacts with no email** — XX,XXX contacts with no email address
   are unbillable dead weight. Run `/delete-no-email-contacts`.
   *Effort: 1 hour | Fully scriptable*

2. **[CRITICAL] Suppress hard bounced contacts** — XX,XXX hard bounces are destroying
   sender reputation. Run `/suppress-hard-bounced`.
   *Effort: 1 hour | Hybrid (API + workflow)*

3. **[HIGH] Reassign deactivated owner contacts** — XX,XXX contacts assigned to
   X deactivated users. Run `/reassign-deactivated-owners`.
   *Effort: 2 hours | Fully scriptable*

4. ...continue ranked by impact...

---

## Detailed Findings

### 1. Database Size

| Metric | Count | % of Total |
|--------|-------|------------|
| Total Contacts | XX,XXX | — |
| Total Companies | XX,XXX | — |
| Total Deals | X,XXX | — |
| Marketing Contacts | XX,XXX | XX% |

### 2. Email Deliverability

| Metric | Count | % of Contacts |
|--------|-------|---------------|
| Hard Bounced | X,XXX | XX% |
| Soft Bounced | X,XXX | XX% |
| Global Unsubscribes | X,XXX | XX% |
| Never Emailed | XX,XXX | XX% |
| Invalid Email Format | XXX | X% |

...continue for all 8 dimensions...

---

## Next Steps

Run `/hubspot-implementation-plan` to generate a phased cleanup plan based on these findings.
```

## Skill Prescription

After generating the audit report, **prescribe a specific ordered list of skills the user should run**. Do not just present findings — tell the user exactly what to do next.

### Step 1: Map Findings to Skills

For each audit finding that scored C or worse, map it to the appropriate skill. Use this category-ordered lookup:

**Database Hygiene** (run first — billing and deliverability impact):
| Finding | Skill | Priority |
|---------|-------|----------|
| Contacts missing email | `/delete-no-email-contacts` | P0 |
| Hard bounced contacts | `/suppress-hard-bounced` | P0 |
| Global unsubscribes | `/suppress-global-unsubscribes` | P0 |
| Ghost/never-engaged contacts | `/suppress-ghost-contacts` | P1 |
| Duplicate companies | `/merge-duplicate-companies` | P1 |
| Deactivated owners with contacts | `/reassign-deactivated-owners` | P1 |

**Data Enrichment** (run second — data quality):
| Finding | Skill | Priority |
|---------|-------|----------|
| Missing company name | `/enrich-company-name` | P1 |
| Missing industry | `/enrich-industry` | P1 |
| Inconsistent geo data | `/standardize-geo-values` | P2 |
| Missing geo data | `/backfill-geo-data` | P2 |
| Missing/wrong lifecycle stage | `/fix-lifecycle-stages` | P1 |
| Unowned marketing contacts | `/assign-unowned-contacts` | P1 |

**Segmentation & Scoring** (run third — targeting):
| Finding | Skill | Priority |
|---------|-------|----------|
| No ICP classification | `/create-icp-tiers` | P2 |
| No lead scoring | `/build-lead-scoring` | P2 |
| No segment lists | `/build-smart-lists` | P2 |

**Automation Workflows** (run fourth — prevention):
| Finding | Skill | Priority |
|---------|-------|----------|
| No new-contact hygiene | `/new-contact-hygiene-workflow` | P2 |
| High disengagement rate | `/engagement-suppression-workflow` | P2 |
| No lifecycle automation | `/lifecycle-progression-workflow` | P3 |
| No bounce monitoring | `/bounce-monitoring-workflow` | P2 |

**Ongoing Maintenance** (run last — sustainability):
| Finding | Skill | Priority |
|---------|-------|----------|
| Unused lists | `/cleanup-lists` | P3 |
| Unused forms | `/cleanup-forms` | P3 |
| Stale workflows | `/cleanup-workflows` | P3 |
| Dashboard clutter | `/cleanup-dashboards` | P3 |
| Deal pipeline issues | `/cleanup-deals` | P3 |
| Unused properties | `/cleanup-properties` | P3 |

### Step 2: Present the Ordered Prescription

After the audit report, present a **numbered action list** — not just findings. Format like this:

```markdown
## Your Cleanup Prescription

Based on the audit, here are the skills you should run, in order:

### Immediate (this week)
1. `/delete-no-email-contacts` — X,XXX contacts with no email are inflating your bill
2. `/suppress-hard-bounced` — X,XXX hard bounces are hurting deliverability
3. `/suppress-global-unsubscribes` — X,XXX unsubscribes still counting as marketing contacts

### Next (weeks 2-3)
4. `/reassign-deactivated-owners` — X deactivated users still own X,XXX contacts
5. `/enrich-company-name` — XX% of contacts missing company name
6. `/fix-lifecycle-stages` — X,XXX contacts in invalid lifecycle stages
...

### Later (weeks 4-6)
7. `/create-icp-tiers` — No ICP classification exists yet
8. `/build-lead-scoring` — No scoring model in place
...
```

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
or jump straight to the first skill: `/delete-no-email-contacts`.
```

## After Running

- Print the file path of the saved report
- Present the ordered skill prescription (Step 2 above)
- Highlight the top 3 most critical findings
- Flag any findings that have no matching skill (Step 3 above)
- Suggest running `/hubspot-implementation-plan` for the full phased plan
