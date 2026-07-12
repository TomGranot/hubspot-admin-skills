---
name: build-lead-scoring
description: "Create a comprehensive lead scoring model with separate Fit and Engagement scores using HubSpot's new Lead Scoring tool. Replaces the deprecated HubSpot Score property."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: segmentation-scoring
---

# Build Lead Scoring Model

Create a two-score lead scoring model using HubSpot's new Lead Scoring tool: a Fit score (ICP company fit + persona match) and an Engagement score (behavioral signals with time decay). This enables sales to prioritize by company fit and marketing to prioritize by engagement recency.

## Why This Matters

Without scoring, every lead looks equally (un)important. Sales has no ranked list of who to call first, marketing cannot trigger stage progressions based on engagement, and there is no way to differentiate between a senior decision-maker at a target-vertical enterprise and a generic contact who has never opened an email.

## Prerequisites

- Super Admin permissions in HubSpot
- HubSpot Marketing Hub Professional or Enterprise
- ICP Tier property created and workflows processed (create-icp-tiers skill must be completed first)
- Access to **Marketing > Lead Scoring** (the new tool, NOT the deprecated "HubSpot Score" property)

## Critical: Old vs New Lead Scoring

**The legacy "HubSpot Score" property was retired on August 31, 2025** — it stopped being editable in July 2025 and stopped updating entirely at the retirement date. Any workflow, list, or report still referencing `hubspotscore` has been running on frozen data since then; part of this skill's job is to find and repoint those references.

The **Lead Scoring tool** (Marketing > Lead Scoring) supports:
- Layered architecture: total score limit → group limits → rules → criteria
- Engagement decay (points reduce over time automatically)
- Separate Fit vs Engagement score types, with time frames and thresholds
- Scoring for **contacts, companies, and deals**
- Up to 5 total scores per portal

**Scores are API-readable.** Configuring scoring rules is still UI-only — there is no scoring configuration API — but each score you create auto-generates CRM properties (the score value and a threshold property). Those properties are readable and filterable through the CRM Search API like any other property, which is what the After stage and the `/lifecycle-progression-workflow` scripts rely on. Find the internal property names under Settings > Properties after creating each score.

## Interview: Gather Requirements

Before executing, collect the following information from the user:

**Q1: What job titles/personas are most valuable to you?**
- Examples: CEO, COO, CFO, CTO, CRO, VP of Operations, VP of Marketing, Director of Operations, Director of Marketing, Head of Procurement, Engineering Manager
- Default: C-suite and VP-level leaders get the highest scores, followed by Director and Manager-level roles

**Q2: What engagement actions matter most?**
- Examples: Email opens, email clicks, form submissions, website visits, content downloads, webinar registrations
- Default: Form submissions (+30), email clicks (+25), website visits (+20), email opens (+15)

**Q3: What negative signals should reduce scores?**
- Examples: Unsubscribe, hard bounce, competitor domain, no activity in 6+ months, free email domain (gmail, yahoo)
- Default: Global unsubscribe (-100), hard bounce (-50), no activity 6+ months (-20), missing company name (-10)

**Q4: What score threshold should trigger MQL status?**
- Examples: Fit > 30 AND Engagement > 20, combined score > 50, any threshold that matches your sales handoff criteria
- Default: Fit Score > 30 AND Engagement Score > 20

## Plan

1. Review any existing scoring models in the portal
2. Create the Fit Score (company fit + persona match)
3. Create or update the Engagement Score (behavioral signals with decay)
4. Allow 4-6 hours for HubSpot to recalculate all contacts
5. Verify scoring distribution and accuracy (after state)

## Before

1. Navigate to **Marketing > Lead Scoring**
2. Note any existing scores (you have a limit of 5 total)
3. Review existing score criteria — decide whether to update or replace
4. Check that ICP Tier property is fully populated on companies (run create-icp-tiers after state check)
5. Search for leftover references to the retired `hubspotscore` property in workflows, lists, and reports — these have been frozen since August 2025 and must be repointed to the new score properties

## Execute

### Create the Fit Score

1. Go to **Marketing > Lead Scoring**
2. Click **Create score**
3. Select **Fit** as the score type
4. Select **Contact** as the scored object
5. Name it descriptively (e.g., "Lead Fit Score")

#### Score Group 1: ICP Company Tier

Use **Associated company property > ICP Tier**:

These are starting points -- calibrate based on your actual conversion data after 30 days.

| Criteria | Condition | Points (suggested range) |
|----------|-----------|------------------------|
| Primary ICP Company | ICP Tier is "Tier 1 - Primary ICP" | +25 to +35 |
| Secondary ICP Company | ICP Tier is "Tier 2 - Secondary ICP" | +15 to +25 |
| Tertiary ICP Company | ICP Tier is "Tier 3 - Tertiary ICP" | +5 to +15 |
| Not ICP Company | ICP Tier is "Not ICP" | -10 to -20 |

#### Score Group 2: Persona / Job Title

Use **Contact property > Job title > contains any of**:

These are starting points -- adjust titles and weights to match your buyer personas.

| Criteria | Example Title Values | Points (suggested range) |
|----------|---------------------|------------------------|
| C-Suite Executives | CEO, COO, CFO, CTO, CRO, CMO, Chief Revenue Officer | +20 to +30 |
| VP-Level Leaders | VP of Operations, VP of Marketing, VP of Sales, VP of Finance | +20 to +30 |
| Director-Level | Director of Operations, Director of Marketing, Head of Procurement, Director of Finance | +15 to +25 |
| Manager-Level | Engineering Manager, Operations Manager, Marketing Manager, Procurement Manager | +10 to +20 |
| Other Relevant Titles | Analyst, Coordinator, Specialist (if relevant to your sales process) | +5 to +10 |

Customize these titles based on your buyer personas. The point values should reflect how likely each persona is to be a decision-maker or champion for your product. The ranges above are starting points -- review after 30 days and adjust based on which titles actually convert.

#### Score Group 3: Negative Fit Signals

| Criteria | Condition | Points |
|----------|-----------|--------|
| Missing Company Name | Company name is unknown | -10 |
| Hard Bounced | Hard bounce reason is known | -50 |
| Globally Unsubscribed | Unsubscribed from all email = True | -100 |

6. Set the overall score maximum (recommended: 100)
7. Save and turn ON

### Create the Engagement Score

1. Click **Create score** (or edit existing engagement score)
2. Select **Engagement** as the score type
3. Select **Contact** as the scored object
4. Name it descriptively (e.g., "Lead Engagement Score")

#### Positive Engagement Criteria

| Criteria | Condition | Points | Decay |
|----------|-----------|--------|-------|
| Opened Marketing Email | Last marketing email open date within last 30 days | +15 | Monthly |
| Clicked Marketing Email | Last marketing email click date within last 30 days | +25 | Monthly |
| Visited Website | Number of Sessions > 0 | +20 | Quarterly |
| Submitted a Form | Number of Form Submissions > 0 | +30 | Quarterly |

#### Negative Engagement Criteria

| Criteria | Condition | Points |
|----------|-----------|--------|
| No Email Activity 6+ Months | Last marketing email open date > 180 days ago | -20 |

5. Set the overall score maximum (recommended: 100)
6. Save and turn ON

### Example Combined Scoring Framework

For reference, here is how the two scores work together to prioritize contacts:

| Contact Profile | Fit Score | Engagement Score | Priority |
|----------------|-----------|-----------------|----------|
| CEO at Tier 1 company, clicked email this week | ~60 | ~55 | Highest |
| Director of Operations at Tier 2 company, form submission | ~40 | ~50 | High |
| Unknown title at Tier 3 company, email open only | ~10 | ~15 | Medium |
| No title, Not ICP, no activity in 6 months | ~-25 | ~-20 | Lowest |

### For Lifecycle Progression

If you want to automatically progress contacts through lifecycle stages based on scoring:

- Define a combined threshold (e.g., Fit Score > 30 AND Engagement Score > 20 = MQL; typically the combined threshold falls in the 40-60 range, but calibrate based on your pipeline)
- Build this as a separate workflow — `/lifecycle-progression-workflow` creates it via the v4 Automation API; set its `LEAD_SCORE_PROPERTY` config to your new score property's internal name
- This is a separate task from building the scoring model

## After

**Allow 4-6 hours for HubSpot to fully recalculate all contact scores.** The new Lead Scoring tool processes asynchronously, and large databases take time.

### Verification

1. Go to **Contacts > Contacts**
2. Click **Edit columns** and add both score properties to visible columns
3. Sort by Fit Score descending

**Check the top 20 contacts:**
- Job titles should be target personas (CEO, VP of Operations, Director of Marketing, etc.)
- Associated companies should be Tier 1 or Tier 2
- If a non-relevant contact appears at the top, review the scoring criteria for issues

**Check the bottom contacts:**
- Sort ascending (lowest scores first)
- Bottom contacts should be unsubscribed, bounced, or at Not ICP companies
- If relevant contacts appear at the bottom, review negative signal weights

**Check score distribution:**
- Filter Fit Score > 50: High-priority fit (should be your best prospects)
- Filter Fit Score 20-50: Medium fit
- Filter Fit Score 1-19: Low fit
- Filter Fit Score <= 0: Disqualified (should be unsubscribed, bounced, or bad data)

**Sanity check:**
- Pick 3 contacts at random
- Manually calculate their expected scores based on your criteria
- Compare to actual scores
- Investigate any discrepancies

**Score distribution via API** (the score properties are searchable like any property — replace the property name with your score's internal name from Settings > Properties):

```python
resp = requests.post(f"{BASE}/crm/v3/objects/contacts/search", headers=HEADERS, json={
    "filterGroups": [{"filters": [
        {"propertyName": "your_fit_score_property", "operator": "GTE", "value": "50"},
    ]}],
    "limit": 1,
})
print(f"Contacts with Fit Score >= 50: {resp.json()['total']}")
```

## Rollback

- Scores can be turned off or deleted in Marketing > Lead Scoring. Deleting a score removes its generated properties — check that no workflows or lists reference them first (especially `/lifecycle-progression-workflow` and any "MQL Ready" lists).
- The retired legacy `hubspotscore` property cannot be revived; there is nothing to roll back to.

## Key Technical Learnings

- **The legacy "HubSpot Score" property is gone (retired August 2025).** Anything still referencing `hubspotscore` runs on frozen data. Repoint it to the new score properties.
- **Score properties are API-readable, configuration is not.** Use the Search API to verify distributions and drive automation off score properties; build and tune the rules in the UI.
- **Two separate scores are better than one.** Fit and Engagement serve different purposes: Fit tells you WHO to talk to (company and persona match), Engagement tells you WHEN to talk to them (behavioral recency). Combining into one number obscures both signals.
- **Score decay is a major improvement.** Enable it on engagement criteria so scores naturally decrease over time. Without decay, a contact who clicked one email two years ago looks the same as one who clicked yesterday.
- **Allow 4-6 hours for recalculation.** Do not panic if scores show 0 immediately after creation. The new tool processes asynchronously across the entire database.
- **Limit of 5 scores per portal.** Plan carefully. You may want to reserve slots for future scores (e.g., product-specific engagement scores).
- **Tune the model after 30 days.** Review whether top-scored contacts are actually converting. Adjust point values based on real conversion data. Lead scoring is iterative, not one-and-done.
- **Negative signals are as important as positive ones.** Hard bounces and global unsubscribes should carry heavy negative weight to push these contacts to the bottom regardless of other factors.
- **ICP Tier is the highest-leverage scoring input.** It captures firmographic fit in a single property. Without it, the Fit score has no company-level signal and relies entirely on persona matching.
