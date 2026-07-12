---
name: audit-api-usage
description: "Inventory the integrations, private apps, and internal tooling that call HubSpot APIs, and flag anything on legacy v1-v4 endpoints ahead of HubSpot's March 30, 2027 end of support. Produces a migration checklist to date-based API versions."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: audit-planning
---

# Audit API Usage Before the 2027 Version Cutoff

In March 2026 HubSpot replaced semantic API versioning (v1-v4) with date-based versions (`/2026-03/`-style paths, two releases a year, 18 months of support each). Everything still calling v1-v4 endpoints — including legacy OAuth v1 — becomes **unsupported on March 30, 2027**. This skill inventories what in your stack calls HubSpot and produces a migration checklist.

## Why This Matters

The deadline fails quietly: unsupported APIs "no longer receive updates, bug fixes, or stability guarantees," and marketplace apps that don't migrate risk losing certification. A portal typically has more callers than anyone remembers — private apps, marketplace apps, middleware (Zapier/Make), form embeds, internal scripts, data warehouse syncs. Finding them takes an afternoon now or an incident later.

## Key Facts

| Fact | Detail |
|------|--------|
| Current recommended version | `2026-03` |
| Release cadence | March and September, every year |
| Support lifecycle | Current (6 months) → Supported (to 18 months) → Unsupported |
| v1–v4 end of support | **March 30, 2027** |
| Also deprecated | Legacy v1 OAuth API (token issuance/introspection) |

## Prerequisites

- Super Admin access (to view Integrations settings and private app logs)
- Optionally: a private app token (`HUBSPOT_ACCESS_TOKEN` in `.env`) for the account-level usage query
- Access to the source code of any internal integrations

## Execution Pattern

### Stage 1: Plan

Confirm with the user: which systems are known to touch HubSpot (CRM syncs, website forms, analytics pipelines, internal scripts), and who owns each.

### Stage 2: Before — Build the Caller Inventory

Work through each discovery source and record every caller in a checklist (owner, what it does, endpoints/versions used):

1. **Private apps**: Settings > Integrations > Private Apps. Open each app > **Logs** — the API call log shows the exact request paths (`/crm/v3/...`, `/contacts/v1/...`), which reveal the version in use.
2. **Connected/marketplace apps**: Settings > Integrations > Connected Apps. You can't see their internals; note each vendor — certified apps are being pushed to migrate by HubSpot, but confirm with the vendor for anything business-critical.
3. **Internal codebases**: grep for version-revealing patterns:
   ```bash
   grep -rEn "api\.hubapi\.com/[a-z-]+/v[0-9]|/contacts/v1|/email/public/v1|hubapi.com/automation/v[23]" .
   ```
4. **Middleware** (Zapier, Make, Workato, n8n): platform-managed connectors migrate on the vendor's schedule; custom HTTP steps inside them do not — check those by hand.
5. **Account-wide API usage** (optional script check): the account-info API reports daily API usage totals for private apps:
   ```python
   resp = requests.get(f"{BASE}/account-info/v3/api-usage/daily", headers=HEADERS)
   ```
   This confirms *how much* traffic flows, not which versions — use the per-app logs from step 1 for version detail.

### Stage 3: Execute — Classify and Plan Migrations

For every caller, classify:

| Status | Meaning | Action |
|--------|---------|--------|
| **Red** | Calls v1/v2 legacy endpoints (e.g., `/contacts/v1/`, `/email/public/v1/`, forms v2) or legacy OAuth v1 | Migrate now — many of these had earlier sunset dates already |
| **Amber** | Calls v3/v4 endpoints | Works until 2027-03-30; schedule migration to `2026-03` date-based paths |
| **Green** | Calls date-based paths, or vendor-managed and confirmed migrating | Monitor |

For amber/red internal code, the migration is usually mechanical — same resources, new path prefix and (sometimes) renamed fields; consult the endpoint's migration notes in HubSpot's docs. Batch the work per codebase, not per endpoint.

This repo's own scripts are **amber** by design: they target `/crm/v3/` and `/automation/v4/`, supported until March 2027, with the migration path documented in `CONTRIBUTING.md`.

### Stage 4: After

1. Every caller in the inventory has a status and an owner.
2. Red items have migration tickets with dates; amber items are scheduled before 2027-03.
3. Re-run this audit every 6 months — each March/September release starts a new support clock.

## Rollback

Read-only — nothing to roll back.

## Technical Gotchas

1. **Private app logs are the ground truth.** Code greps miss dynamically-built URLs; the per-app request logs in Settings show what is actually being called.
2. **404 vs 403 vs unsupported.** After end of support, endpoints may keep working for a while — "unsupported" means no fixes or guarantees, not an instant shutoff. Do not treat "it still works" as "we're fine."
3. **OAuth is part of this.** Apps using legacy v1 OAuth token endpoints must move to the date-based OAuth API even if their data endpoints are current.
4. **SDK versions pin API versions.** If an integration uses an official HubSpot SDK, the SDK's major version determines which API version it calls — check the SDK changelog, not just your code.
