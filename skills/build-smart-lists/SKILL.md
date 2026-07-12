---
name: build-smart-lists
description: "Create foundational segmented lists for marketing and sales operations via the Lists API, plus advanced UI-built segments: a master sendable list, ICP-based lists, persona lists, and engagement lists. All active (dynamic) lists."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: segmentation-scoring
---

# Build Smart Lists for Segmentation

Create the core active (dynamic) lists that serve as the foundation for all marketing campaigns, sales prioritization, and database health monitoring. Ten foundation lists are created automatically via the Lists API (v3); a further set of advanced segments is built in the UI.

## Why This Matters

Without predefined lists, every email campaign requires building filters from scratch, there is no standardized definition of "who can we actually email", and there is no persona-based segmentation. The marketing team cannot quickly answer basic questions like "How many senior decision-makers can we email right now?" or "How many engaged contacts do we have?"

## Prerequisites

- Super Admin or Marketing Hub Admin permissions
- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with `crm.lists.read` and `crm.lists.write` scopes
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- ICP Tier property created and workflows processed (create-icp-tiers skill) — the script assumes the property name `company_segment` with values like `tier_1_primary_icp`; adjust its configuration block if yours differ
- Lead scoring model created (build-lead-scoring skill) is recommended but not required
- Lifecycle Stage property populated for customers and partners (fix-lifecycle-stages skill)

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Execute | [`scripts/execute.py`](./scripts/execute.py) | `uv run skills/build-smart-lists/scripts/execute.py` |

`execute.py` creates the 10 foundation lists below via `POST /crm/v3/lists`, skips lists that already exist (409), and writes a CSV audit trail of created list IDs. There are no before/after scripts: the before-state inventory is a single Lists API query (see Before), and verification is a member-count review in the UI.

## Interview: Gather Requirements

Before executing, collect the following information from the user:

**Q1: What defines "engaged" for your business? (e.g., activity in last 60-120 days)**
- Examples: Email open or click in last 90 days, website visit in last 60 days, form submission in last 30 days
- Default: Email open or click in the last 90 days (set `ACTIVE_WINDOW_DAYS` in the script; shorter cycles suit high-velocity sales, longer cycles suit enterprise)

**Q2: What job titles represent your target personas?**
- Examples: CEO, COO, CFO, CTO, CRO, VP of Operations, VP of Marketing, Director of Operations, Director of Marketing, Head of Procurement, Engineering Manager
- Default: C-suite and VP/Director-level leaders across business functions (used for the UI-built persona list)

## The List Library

### Foundation lists (created by the script)

| # | List Name | Object | Key Filter |
|---|-----------|--------|-----------|
| 1 | All Marketing Contacts | Contacts | `hs_marketable_status` = true |
| 2 | All Leads | Contacts | Lifecycle stage = Lead |
| 3 | All MQLs | Contacts | Lifecycle stage = MQL |
| 4 | All SQLs | Contacts | Lifecycle stage = SQL |
| 5 | All Customers | Contacts | Lifecycle stage = Customer |
| 6 | ICP Tier 1 Companies | Companies | ICP Tier = Tier 1 |
| 7 | ICP Tier 2 Companies | Companies | ICP Tier = Tier 2 |
| 8 | ICP Tier 3 Companies | Companies | ICP Tier = Tier 3 |
| 9 | Engaged Last 90 Days | Contacts | Email open OR click within the active window |
| 10 | Unengaged 180+ Days | Contacts | Marketable + no email open beyond the re-engagement window |

### Advanced segments (built in the UI)

These use features that benefit from human judgment and portal-specific configuration (list-membership filters, persona keywords, form-name keywords):

| # | List Name | Purpose | Key Filters |
|---|-----------|---------|-------------|
| A | Marketable - Active | Master sendable list (who CAN receive email) | Marketing contact + not unsubscribed + not bounced + has email + not quarantined |
| B | ICP Tier 1 Contacts | Highest priority *contacts* | Associated company ICP Tier = Tier 1 + member of Marketable - Active |
| C | ICP Tier 2 Contacts | Secondary priority contacts | Associated company ICP Tier = Tier 2 + member of Marketable - Active |
| D | Partners | Partner communications and exclusion | Lifecycle stage = Partner (or custom contact type property) |
| E | Re-engagement Needed | Sunset candidates | 5+ emails delivered + no open in 180 days + member of Marketable - Active |
| F | Senior Decision Makers | Top persona list | Job title contains target titles |
| G | Industry Leaders | Contacts at companies in target verticals | Associated company industry is any of target industries |
| H | Content Engaged | Form submissions and content downloads | Form submissions > 0 OR conversion contains content keywords |

Overlap note: "All Customers" (script) covers the Customers use case; "Unengaged 180+ Days" (script) is a simpler variant of "Re-engagement Needed" (UI, adds the delivered-count guard). Keep whichever fits your operation — do not maintain both without a reason.

## Plan

1. Run the interview above; set `ACTIVE_WINDOW_DAYS`, `REENGAGEMENT_WINDOW_DAYS`, and `ICP_PROPERTY_NAME` in the script's configuration block
2. Decide which advanced segments to build in the UI
3. Create foundation lists via the script, advanced segments via the UI
4. Verify list sizes make sense relative to the database

## Before

Inventory existing lists to avoid duplicates (`POST /crm/v3/lists/search` with an empty query returns all lists, paginated). Check for name collisions with the library above — the script skips exact name matches (HTTP 409), but near-duplicates ("Customers" vs "All Customers") need a human decision: merge, rename, or skip.

## Execute

### Step 1: Foundation lists (script)

```bash
uv run skills/build-smart-lists/scripts/execute.py
```

The script posts each definition to `POST /crm/v3/lists` with `processingType: "DYNAMIC"`. Example payload shape (see the script for all ten):

```python
{
    "name": "All Customers",
    "objectTypeId": "0-1",  # contacts ("0-2" for companies)
    "processingType": "DYNAMIC",
    "filterBranch": {
        "filterBranchType": "AND",
        "filterBranches": [],
        "filters": [{
            "filterType": "PROPERTY",
            "property": "lifecyclestage",
            "operation": {
                "operationType": "ENUMERATION",
                "operator": "IS_EQUAL_TO",
                "value": "customer",
            },
        }],
    },
}
```

If the Lists API returns 403 on your plan tier, build the same lists manually in the UI using the table above.

### Step 2: Marketable - Active (master sendable list — UI)

**This is the most important advanced list.** It defines the single source of truth for "who can receive marketing email." All campaign sends should reference this list.

1. Go to **Contacts > Lists > Create list**
2. Select **Contact-based > Active list**
3. Name: `Marketable - Active`
4. Add filters (all AND logic):
   - Marketing contact status > is any of > Marketing contact
   - AND Unsubscribed from all email > is not equal to > True
   - AND Hard bounce reason > is unknown
   - AND Email > is known
   - AND Email quarantined > is not equal to > True
5. Save the list

### Step 3: Remaining advanced segments (UI)

**ICP Tier 1 / Tier 2 Contacts (B, C):**
- Filters: Associated company property > ICP Tier > is any of > [tier] AND List membership > is member of > Marketable - Active
- **Using List membership as a filter** is a powerful pattern: these lists automatically inherit all deliverability and consent logic from Marketable - Active. New disqualification conditions added there propagate automatically.

**Partners (D):** Lifecycle stage > is any of > Partner. Always exclude from prospect campaigns.

**Re-engagement Needed (E):**
- Marketing emails delivered > is greater than > 5
- AND Last marketing email open date > is more than > 180 days ago (tune to your cycle: 120-270)
- AND List membership > is member of > Marketable - Active
- Feeds the engagement-based suppression workflow.

**Senior Decision Makers (F):** Job title > contains any of > [your target titles]. Customize keywords to your buyer personas.

**Industry Leaders (G):** Associated company property > Industry > is any of > [your target industries].

**Content Engaged (H):** OR logic between groups:
- Number of Form Submissions > is greater than > 0
- OR First conversion > contains any of > [content keywords like "Download", "Guide", "Checklist", "E-Book", "Whitepaper"]
- OR Recent conversion > contains any of > [same keywords]
- The conversion-based filters depend on your form naming conventions — review actual form names (Marketing > Forms) and adjust.

## After

### Verify List Sizes

After all lists are created and processed:

| List | Expected Range | Red Flag If... |
|------|---------------|----------------|
| All Marketing Contacts / Marketable - Active | 30-80% of total contacts | Below 10% (too many excluded) or above 90% (filters too loose) |
| ICP Tier lists | 2-10% of marketable | 0 (ICP Tier not populated) |
| Engaged (active window) | 5-30% of total contacts | Below 2% (possible engagement tracking issue) |
| All Customers | Known customer count | Off by more than 20% from expected |
| Partners | Known partner count | Off by more than 20% from expected |
| Unengaged / Re-engagement Needed | 10-40% of marketable | Above 60% (possible date threshold issue) |
| Senior Decision Makers | 5-25% of total contacts | 0 (job title data missing) |
| Industry Leaders | 10-50% of total contacts | 0 (industry data missing) |
| Content Engaged | 1-10% of total contacts | 0 (no form submissions or wrong keywords) |

### Verification Checklist

1. **All lists show as Active** (not Static) in the list view
2. **All lists have completed processing** (no "Processing" status)
3. **Sendable-list sanity check:** Open Marketable - Active (or All Marketing Contacts), click 5 random contacts. Each should have a valid email, not be unsubscribed, not be bounced.
4. **ICP list check:** Open an ICP Tier 1 list, click 5 records. Each should have ICP Tier = Tier 1.
5. **Persona list check:** Open Senior Decision Makers, verify job titles match expected patterns. Watch for false positives (e.g., "Marketing Intern" matching on "Marketing").
6. **Re-engagement check:** Verify contacts have 5+ emails delivered and no open beyond your configured window.

## Rollback

- Lists can be deleted via `DELETE /crm/v3/lists/{listId}` or the UI — the script's CSV audit trail records every list ID it created.
- Deleting a list does not affect the contacts in it — only the list definition is removed.
- Check whether any workflows, emails, or dependent lists (list-membership filters!) reference a list before deleting it.

## Key Technical Learnings

- **The master sendable list is the foundation.** Every email campaign should either send directly to it (with additional filters) or use it as an inclusion filter. Never send to a list that does not incorporate deliverability and consent checks.
- **List membership as a filter is a powerful pattern.** Changes to the master list's criteria automatically propagate to all dependent lists.
- **"Contains any of" for job titles is broad by design.** It matches the keyword anywhere in the title string, so "CTO" matches "CTO", "Former CTO", "Assistant to the CTO". Review lists periodically and add exclusion terms (e.g., AND Job title does not contain "Former", "Assistant", "Intern") if false positives become a problem.
- **Content and event lists depend on form naming conventions.** The keyword-based filters only work if forms follow a naming convention that includes the keywords. After creating the lists, check if counts seem too low and adjust keywords to match actual form names.
- **Active lists have a processing delay.** HubSpot processes active lists periodically (every few minutes for small lists, potentially longer for complex ones). Wait for processing to complete before judging counts.
- **Each list should be active (dynamic), not static.** Static lists are snapshots that never update. Active lists update automatically as contact properties change, which is essential for ongoing segmentation.
- **The ICP property name and values must match the create-icp-tiers skill.** The script defaults to property `company_segment` with values `tier_1_primary_icp` / `tier_2_secondary_icp` / `tier_3_tertiary_icp`. If you chose different names, update the script's configuration block before running.
- **Plan for growth.** These lists cover core use cases. As marketing operations mature, add more targeted lists: "MQL Ready" (score threshold), "Competitor Employees" (for exclusion), "Recent Form Submitters (Last 30 Days)" (for fast follow-up), or service/product-specific interest lists.
- **Build a dashboard.** Create a dashboard with one KPI tile per list showing the current count. This gives at-a-glance visibility into segment health and makes it easy to spot sudden changes (e.g., Marketable list drops 50% = something broke).
