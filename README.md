# HubSpot Admin Skills for Claude Code

<p align="center">
  <img src="./assets/hero.png" alt="CRM Autopilot — HubSpot Admin Skills" width="100%" />
</p>

**36 Claude Code skills for auditing, cleaning, enriching, and automating your HubSpot CRM**

[![Website](https://img.shields.io/badge/site-hubspot.granot.io-ff7a59)](https://hubspot.granot.io)
[![Skills](https://img.shields.io/badge/skills-36-blue)](./skills/)
[![License](https://img.shields.io/badge/license-MIT-green)](./LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-compatible-blueviolet)](https://claude.com/claude-code)

📖 **Browse every skill with full docs at [hubspot.granot.io](https://hubspot.granot.io)** — including [common problems mapped to fixes](https://hubspot.granot.io/problems) and [agent-readable endpoints](https://hubspot.granot.io/install#agents) (`llms.txt`, `skills.json`).

Built by [Tom Granot](https://consume.granot.io) — from deep experience with enterprise HubSpot CRM administration.

---

## What's New in 1.1

HubSpot's platform moved fast in 2026, and this release moves with it:

- **Workflows are now API-first.** HubSpot's v4 Automation API is stable (v3 is legacy), so the four workflow-builder skills now *create* their workflows via scripts — always disabled, for review in the UI before enabling — instead of walking you through 40 clicks. Nested branch designs are decomposed into small linear flows the API expresses cleanly.
- **New `/workflows-as-code`** — export every workflow to versioned JSON, diff exports, restore from backup. HubSpot has no workflow recycle bin; now you have one.
- **Official MCP support.** HubSpot's remote MCP server went GA in April 2026; `/connect-hubspot-mcp` wires it into Claude Code for conversational spot-checks alongside the bulk scripts.
- **New `/waterfall-enrich-contacts`** — external enrichment with pluggable provider adapters (FullEnrich waterfall by default; Apollo, Hunter, Dropcontact included; bring your own), cost caps, and a no-overwrite safety model.
- **New `/audit-api-usage`** — HubSpot switched to date-based API versioning (`2026-03`) and legacy v1–v4 endpoints lose support on March 30, 2027. This skill finds everything in your stack that needs migrating.
- **Lead scoring refreshed** for the post-2025 scoring tool (Fit + Engagement scores, decay, API-readable score properties), plus repo-wide consistency fixes — one env var, one Python house style, scripts linked from every skill. See [CHANGELOG.md](./CHANGELOG.md).

---

## Connecting to HubSpot

The skills use two complementary connection paths:

1. **Private app token + scripts (the default).** Every scripted skill runs plain-Python `requests` against HubSpot's REST APIs using a private app token (`HUBSPOT_ACCESS_TOKEN` in `.env`). This is the path for bulk operations — it gives you pagination, rate-limit handling, abort thresholds, and CSV audit trails.
2. **HubSpot's official MCP server (optional, interactive).** Connect Claude Code to `mcp.hubspot.com` via OAuth for conversational reads and spot-checks — "show me 5 contacts this cleanup touched" — without writing a script. Run `/connect-hubspot-mcp` to set it up and to see the full division of labor.

Audits, hygiene, enrichment, and segmentation run on scripts; use MCP alongside them for verification and triage.

## Quick Start

### 1. Install

```bash
# Add the marketplace
/plugin marketplace add tomgranot/hubspot-admin-skills

# Install the plugin
/plugin install hubspot-admin@hubspot-admin-skills
```

Or clone directly: `git clone https://github.com/TomGranot/hubspot-admin-skills.git`

### 2. Audit your portal

```
/hubspot-audit
```

This scans your entire HubSpot portal — contacts, companies, deals, engagement, deliverability, data quality, duplicates, owners, lists, workflows — and produces a graded report. Each finding gets a severity rating (A-F) and is mapped to the specific skill that fixes it.

### 3. Get your cleanup plan

```
/hubspot-implementation-plan
```

Reads your audit report and generates a phased roadmap: what to fix, in what order, which skill to run, how long it takes, and what can be automated vs. what needs manual UI work. The plan sequences tasks by dependency — you can't score leads before enriching company data, and you can't build ICP tiers before standardizing industries.

### 4. Execute skill by skill

The plan tells you exactly which slash command to run next. Each skill follows a 4-stage pattern:

| Stage | What happens |
|-------|-------------|
| **Plan** | Explains the approach, asks you for any configuration needed |
| **Before** | Audits current state, exports CSV baseline, shows you what will change |
| **Execute** | Makes the changes (API scripts or step-by-step UI instructions) |
| **After** | Verifies the fix, compares before/after, confirms success |

Skills that can be scripted include ready-to-run Python scripts (plain `requests`, run with `uv run` — no project setup needed). Skills that require HubSpot UI work (lead scoring, some workflow options) provide precise build instructions.

### 5. Maintain

Once clean, use `/weekly-cleanup-routine` (5 min/week) and `/quarterly-database-cleanup` to keep it that way. The audit skill detects issues that no existing skill covers and offers to create new ones on the spot.

---

## Skills Reference

### Audit & Planning (4)

| Skill | Description |
|-------|-------------|
| [`hubspot-audit`](https://hubspot.granot.io/skills/hubspot-audit) | Run a comprehensive audit of your HubSpot portal — contacts, companies, deals, properties, lists, workflows, and forms |
| [`hubspot-implementation-plan`](https://hubspot.granot.io/skills/hubspot-implementation-plan) | Generate a phased implementation plan from audit findings with prioritized action items |
| [`connect-hubspot-mcp`](https://hubspot.granot.io/skills/connect-hubspot-mcp) | Connect Claude Code to HubSpot's official remote MCP server for conversational CRM reads and spot-checks |
| [`audit-api-usage`](https://hubspot.granot.io/skills/audit-api-usage) | Find every integration calling legacy v1–v4 HubSpot endpoints before the March 2027 end of support |

### Database Hygiene (6)

| Skill | Description |
|-------|-------------|
| [`delete-no-email-contacts`](https://hubspot.granot.io/skills/delete-no-email-contacts) | Identify and delete contacts that have no email address — unusable records that inflate your database |
| [`suppress-hard-bounced`](https://hubspot.granot.io/skills/suppress-hard-bounced) | Suppress contacts with hard-bounced email addresses to protect sender reputation |
| [`suppress-global-unsubscribes`](https://hubspot.granot.io/skills/suppress-global-unsubscribes) | Suppress globally unsubscribed contacts to ensure compliance and reduce wasted marketing spend |
| [`suppress-ghost-contacts`](https://hubspot.granot.io/skills/suppress-ghost-contacts) | Find and suppress ghost contacts — records with no activity, no engagement, and no business value |
| [`merge-duplicate-companies`](https://hubspot.granot.io/skills/merge-duplicate-companies) | Detect and merge duplicate company records using domain matching and fuzzy name comparison |
| [`reassign-deactivated-owners`](https://hubspot.granot.io/skills/reassign-deactivated-owners) | Reassign contacts and deals owned by deactivated HubSpot users to active team members |

### Data Enrichment (6)

| Skill | Description |
|-------|-------------|
| [`enrich-company-name`](https://hubspot.granot.io/skills/enrich-company-name) | Populate missing company names on contacts by pulling from their associated company records |
| [`enrich-industry`](https://hubspot.granot.io/skills/enrich-industry) | Backfill contact industry values from associated company industry data |
| [`standardize-geo-values`](https://hubspot.granot.io/skills/standardize-geo-values) | Normalize country and state/region values to consistent formats across your database |
| [`assign-unowned-contacts`](https://hubspot.granot.io/skills/assign-unowned-contacts) | Assign marketing contacts that have no owner to the appropriate team members based on territory or segment rules |
| [`fix-lifecycle-stages`](https://hubspot.granot.io/skills/fix-lifecycle-stages) | Detect and correct lifecycle stage violations — contacts stuck in the wrong stage or regressed backwards |
| [`waterfall-enrich-contacts`](https://hubspot.granot.io/skills/waterfall-enrich-contacts) | Enrich emails, phones, and titles via external providers — FullEnrich waterfall by default, Apollo/Hunter/Dropcontact included, or bring your own |

### Segmentation & Scoring (3)

| Skill | Description |
|-------|-------------|
| [`create-icp-tiers`](https://hubspot.granot.io/skills/create-icp-tiers) | Create an ICP (Ideal Customer Profile) tier property and assign tier values based on firmographic criteria |
| [`build-lead-scoring`](https://hubspot.granot.io/skills/build-lead-scoring) | Design and implement a lead scoring model in HubSpot's Lead Scoring tool — separate Fit and Engagement scores with decay |
| [`build-smart-lists`](https://hubspot.granot.io/skills/build-smart-lists) | Build active smart lists for key segments — ICP tiers, lifecycle stages, engagement levels, and suppression groups |

### Automation Workflows (5)

All four builders create their workflows via the stable v4 Automation API (always disabled, for UI review before enabling), with a manual UI path as fallback.

| Skill | Description |
|-------|-------------|
| [`new-contact-hygiene-workflow`](https://hubspot.granot.io/skills/new-contact-hygiene-workflow) | Build a workflow that screens new contacts on creation — validates email, enriches data, and assigns owners |
| [`engagement-suppression-workflow`](https://hubspot.granot.io/skills/engagement-suppression-workflow) | Create a two-tier sunset system that re-engages dormant contacts before suppressing them |
| [`lifecycle-progression-workflow`](https://hubspot.granot.io/skills/lifecycle-progression-workflow) | Set up automated lifecycle stage progression based on engagement thresholds and sales activity |
| [`bounce-monitoring-workflow`](https://hubspot.granot.io/skills/bounce-monitoring-workflow) | Build workflows that monitor bounce events and auto-suppress contacts exceeding bounce thresholds |
| [`workflows-as-code`](https://hubspot.granot.io/skills/workflows-as-code) | Export all workflows to versioned JSON, diff exports over time, and restore workflows from backup |

### Ongoing Maintenance (12)

| Skill | Description |
|-------|-------------|
| [`quarterly-database-cleanup`](https://hubspot.granot.io/skills/quarterly-database-cleanup) | Run a quarterly hygiene sweep — re-audit contacts, prune stale records, and refresh suppression lists |
| [`review-bounced-contacts`](https://hubspot.granot.io/skills/review-bounced-contacts) | Review contacts with 3+ bounces and decide on suppression or re-verification |
| [`cleanup-lists`](https://hubspot.granot.io/skills/cleanup-lists) | Audit and archive unused, redundant, or stale lists cluttering your portal |
| [`cleanup-forms`](https://hubspot.granot.io/skills/cleanup-forms) | Review forms for unused, broken, or duplicate entries and recommend consolidation |
| [`cleanup-workflows`](https://hubspot.granot.io/skills/cleanup-workflows) | Identify workflows that are off, broken, or redundant and recommend which to archive or fix |
| [`weekly-cleanup-routine`](https://hubspot.granot.io/skills/weekly-cleanup-routine) | A repeatable weekly checklist covering the highest-impact maintenance tasks |
| [`cleanup-dashboards`](https://hubspot.granot.io/skills/cleanup-dashboards) | Audit dashboards for unused, duplicate, or outdated reports and recommend consolidation |
| [`cleanup-deals`](https://hubspot.granot.io/skills/cleanup-deals) | Review deal pipeline hygiene — stale deals, missing properties, and stage violations |
| [`cleanup-properties`](https://hubspot.granot.io/skills/cleanup-properties) | Find unused, duplicate, or poorly named contact/company/deal properties and recommend cleanup |
| [`cleanup-lead-owners`](https://hubspot.granot.io/skills/cleanup-lead-owners) | Audit lead owner assignments for imbalances, orphaned records, and routing issues |
| [`backfill-geo-data`](https://hubspot.granot.io/skills/backfill-geo-data) | Backfill missing country and state values using IP geolocation, form submissions, and company data |
| [`create-segment-lists`](https://hubspot.granot.io/skills/create-segment-lists) | Create a standard set of segment lists for reporting, targeting, and suppression |

---

## Prerequisites

- **Claude Code** installed and configured
- **HubSpot account** with a private app token in `.env` as `HUBSPOT_ACCESS_TOKEN`. Typical scopes across the skill set: `crm.objects.contacts.read/write`, `crm.objects.companies.read/write`, `crm.objects.deals.read/write`, `crm.objects.owners.read`, `crm.schemas.*` (property management), `crm.lists.read/write`, `automation` (workflow skills), `forms` — grant per skill as documented in each SKILL.md
- **Python 3.10+** with [uv](https://github.com/astral-sh/uv) — scripts carry inline metadata and run with `uv run`, no project setup
- HubSpot **Marketing Professional** plan or higher (for workflow-based skills)
- Optional: HubSpot's **MCP server** connection for conversational spot-checks (`/connect-hubspot-mcp`)
- Optional: an **enrichment provider** API key (FullEnrich, Apollo, Hunter, Dropcontact, or your own) for `/waterfall-enrich-contacts`

### API versioning

Scripts target HubSpot's stable REST versions: `/crm/v3/`, `/automation/v4/`, `/marketing/v3/` — all supported until **March 30, 2027**. HubSpot's current recommended target is the date-based `2026-03` release; this repo will migrate in a future major version, and `/audit-api-usage` helps you migrate everything else in your stack.

---

## Directory Structure

```
hubspot-admin-skills/
├── README.md
├── CLAUDE.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE
├── .gitignore
├── assets/
│   └── hero.png
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
└── skills/
    ├── hubspot-audit/
    │   ├── SKILL.md
    │   └── scripts/
    │       └── audit_portal.py
    ├── hubspot-implementation-plan/
    │   └── SKILL.md
    ├── delete-no-email-contacts/
    │   ├── SKILL.md
    │   └── scripts/
    │       ├── before.py
    │       ├── execute.py
    │       └── after.py
    ├── suppress-hard-bounced/
    │   ├── SKILL.md
    │   └── scripts/
    │       ├── before.py
    │       └── after.py
    ├── waterfall-enrich-contacts/
    │   ├── SKILL.md
    │   └── scripts/
    │       ├── before.py / execute.py / after.py
    │       └── providers/           (fullenrich, apollo, hunter, dropcontact, _template)
    ├── ...                        (36 skills total, 20 with scripts)
    └── backfill-geo-data/
        └── SKILL.md
```

---

## Community-Driven: Help Build the Skill Set

Every HubSpot portal is different. The audit skill will automatically detect issues that aren't covered by existing skills and **offer to create new ones on the spot**. When it does, it will ask:

> *"Would you like to contribute this new skill back to the community? It will help other HubSpot admins facing the same issue."*

If you say yes, Claude Code will create the skill, push it to your fork, and open a PR — all automatically. You don't need to know git or write markdown.

### Manual Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the full skill template, frontmatter spec, Python house style, safety-mechanism requirements, and category list. The short version:

1. **Fork**: `gh repo fork TomGranot/hubspot-admin-skills --clone`
2. **Branch**: `git checkout -b skill/your-skill-name`
3. **Create**: Add `skills/<your-skill>/SKILL.md` following the 4-stage pattern (**Plan** → **Before** → **Execute** → **After**, plus **Rollback**)
4. **Test**: Run the skill against a HubSpot sandbox portal
5. **PR**: `gh pr create --repo TomGranot/hubspot-admin-skills`

Please keep skills generic and company-agnostic. No customer data, API keys, or proprietary information.

---

## Author

Created by **[Tom Granot](https://consume.granot.io)**. Built from extensive experience administering HubSpot CRM at scale.

---

## License

MIT -- see [LICENSE](./LICENSE) for details.
