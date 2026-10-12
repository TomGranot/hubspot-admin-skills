---
name: audit-api-usage
description: "Inventory the integrations, service keys, legacy private apps, and internal tooling that call HubSpot APIs, and flag anything on legacy v1-v4 endpoints or legacy app architecture ahead of HubSpot's 2027 cutoffs. Produces a migration checklist to date-based API versions and service keys."
license: MIT
metadata:
  author: tomgranot
  version: "1.2"
  category: audit-planning
---

# Audit API Usage Before the 2027 Cutoffs

In March 2026 HubSpot replaced semantic API versioning (v1-v4) with date-based versions (`/2026-09/`-style paths, two releases a year, at least 18 months of support each). Two clocks are now running: **v4 loses support on March 30, 2027**, and **v1-v3 are already unsupported, with enforcement in September 2027**. Separately, HubSpot is retiring legacy private apps in favor of service keys. This skill inventories what in your stack calls HubSpot and produces a migration checklist for both.

## Why This Matters

The deadline fails quietly: unsupported APIs "no longer receive updates, bug fixes, or stability guarantees," and marketplace apps that don't migrate risk losing certification. A portal typically has more callers than anyone remembers — service keys, legacy private apps, marketplace apps, middleware (Zapier/Make), form embeds, internal scripts, data warehouse syncs. Finding them takes an afternoon now or an incident later.

## Key Facts

| Fact | Detail |
|------|--------|
| Current version | `2026-09` (for example `/crm/objects/2026-09/contacts`) |
| Release cadence | March and September, every year; each version is immutable |
| Support lifecycle | At least 18 months per version |
| v4 end of support | **March 30, 2027** |
| v1-v3 status | **Unsupported since September 15, 2026** (no bug fixes, reliability, or security updates); enforcement **September 2027** |
| Legacy private apps | Creation disabled **October 26, 2026** for existing accounts (September 28, 2026 for new ones). Existing apps keep working and must migrate by September 2027 |
| Replacement for private apps | **Service keys** (Settings > Integrations > Service Keys): bearer tokens for REST calls, no webhooks |
| Also deprecated | Legacy v1 OAuth API (token issuance/introspection) |
| Behavior change in `2026-09` | CRM writes enforce admin-configured required and conditionally required properties, returning HTTP 400 where v3 accepted the write |

Sources: HubSpot developer changelog, "Introducing date-based API versioning" (2026-03-30), "Deprecating support for HubSpot v4 APIs" (2026-05-21), "Legacy private app creation sunset" (2026-08-27), and "Legacy APIs and legacy apps: what's going unsupported and when" (2026-09-15). Re-check these before quoting dates to stakeholders; HubSpot has moved sunset dates before.

## Prerequisites

- Super Admin access (to view Integrations settings and app logs)
- Optionally: a service key or existing legacy private app token (`HUBSPOT_ACCESS_TOKEN` in `.env`) for the account-level usage query
- Access to the source code of any internal integrations

## Execution Pattern

### Stage 1: Plan

Confirm with the user: which systems are known to touch HubSpot (CRM syncs, website forms, analytics pipelines, internal scripts), and who owns each.

### Stage 2: Before — Build the Caller Inventory

Work through each discovery source and record every caller in a checklist (owner, what it does, endpoints/versions used):

1. **Legacy private apps and service keys**: Settings > Integrations > Private Apps, and Settings > Integrations > Service Keys. Open each legacy app > **Logs**: the API call log shows the exact request paths (`/crm/v3/...`, `/contacts/v1/...`), which reveal the version in use. Record every legacy private app as a migration item in its own right, whatever endpoints it calls.
2. **Connected/marketplace apps**: Settings > Integrations > Connected Apps. You can't see their internals; note each vendor — certified apps are being pushed to migrate by HubSpot, but confirm with the vendor for anything business-critical.
3. **Internal codebases**: grep for version-revealing patterns:
   ```bash
   grep -rEn "api\.hubapi\.com/[a-z-]+/v[0-9]|/contacts/v1|/email/public/v1|hubapi.com/automation/v[23]" .
   ```
4. **Middleware** (Zapier, Make, Workato, n8n): platform-managed connectors migrate on the vendor's schedule; custom HTTP steps inside them do not — check those by hand.
5. **Account-wide API usage** (optional script check): the account-info API reports daily API usage totals for privately distributed apps:
   ```python
   resp = requests.get(f"{BASE}/account-info/v3/api-usage/daily", headers=HEADERS)
   ```
   This confirms *how much* traffic flows, not which versions — use the per-app logs from step 1 for version detail.

### Stage 3: Execute — Classify and Plan Migrations

For every caller, classify:

| Status | Meaning | Action |
|--------|---------|--------|
| **Red** | Calls v1/v2 legacy endpoints (e.g., `/contacts/v1/`, `/email/public/v1/`, forms v2) or legacy OAuth v1 | Migrate now. Many of these have already been shut off (Contact Lists v1 returns 404 since April 30, 2026; Pipelines v1 sunsets December 4, 2026) |
| **Amber (v4)** | Calls `/v4/` endpoints, such as `/automation/v4/flows` or `/crm/v4/` associations | Supported until 2027-03-30; migrate to date-based paths before then |
| **Amber (v3)** | Calls `/v3/` endpoints | Already unsupported, still working; migrate to `2026-09` date-based paths before September 2027 |
| **Amber (app)** | Runs on a legacy private app token, whatever it calls | Move to a service key before September 2027 |
| **Green** | Calls date-based paths with a service key or a projects-based app, or vendor-managed and confirmed migrating | Monitor |

For amber/red internal code, the migration is usually mechanical: same resources, new path shape (`/crm/v3/objects/contacts` becomes `/crm/objects/2026-09/contacts`) and sometimes renamed fields. HubSpot's migration guide says many v3 contracts carry over unchanged but not all, so test each endpoint rather than assuming. Batch the work per codebase, not per endpoint.

Test writes in particular. From `2026-09`, a create or update that omits a property an admin marked required is rejected with `MISSING_REQUIRED_PROPERTY` or `MISSING_CONDITIONAL_REQUIRED_PROPERTY`. An integration that wrote sparse records through v3 will start failing after migration unless it sends those properties.

This repo's own scripts are **amber**: they target `/crm/v3/`, `/marketing/v3/`, and `/automation/v4/`. They work today, and they are on the migration list in `CONTRIBUTING.md` like everyone else's.

### Stage 4: After

1. Every caller in the inventory has a status and an owner.
2. Red items have migration tickets with dates; v4 callers are scheduled before 2027-03, v3 callers and legacy private apps before 2027-09.
3. Re-run this audit every 6 months — each March/September release starts a new support clock.

## Rollback

Read-only — nothing to roll back.

## Technical Gotchas

1. **App logs are the ground truth.** Code greps miss dynamically-built URLs; the per-app request logs in Settings show what is actually being called.
2. **404 vs 403 vs unsupported.** After end of support, endpoints may keep working for a while — "unsupported" means no fixes or guarantees, not an instant shutoff. Do not treat "it still works" as "we're fine."
3. **You cannot create a new private app as a stopgap.** After October 26, 2026 the option is gone for existing accounts. A new internal integration needs a service key from day one.
4. **Service keys do not receive webhooks.** An integration that relies on webhook subscriptions needs a projects-based app, not a service key.
5. **OAuth is part of this.** Apps using legacy v1 OAuth token endpoints must move to the date-based OAuth API even if their data endpoints are current.
6. **SDK versions pin API versions.** If an integration uses an official HubSpot SDK, the SDK's major version determines which API version it calls — check the SDK changelog, not just your code.
