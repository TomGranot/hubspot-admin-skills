# Changelog

## 1.2.0 — 2026-07-12

Self-testing release: the toolkit can now prove itself against a disposable portal you bring.

### New skill (36 → 37)

- **`sandbox-self-test`** (audit-planning) — bring-your-own developer sandbox test harness:
  - `preflight.py` gates on `GET /account-info/v3/details` — runs **only** against `DEVELOPER_TEST`/`SANDBOX` portals, fails closed, no override; probes required scopes.
  - `seed.py` creates a marker-tagged synthetic fixture matrix (reserved `.invalid` email domain, `SELFTEST` prefixes), one defect per testable skill; idempotent.
  - `run_suite.py` smoke-tests every scripted skill's `before.py`, runs end-to-end cases (`delete-no-email-contacts` destructive cycle, `waterfall-enrich-contacts` with the new mock provider, `workflows-as-code` export) and API round-trips (dynamic list, disabled v4 workflow); writes `reports/selftest-{date}.md`; sandbox-unsimulatable areas (bounce state, `hs_email_optout`, `hs_marketable_status`, deactivated owners) are reported as SKIP with reasons, never silently omitted.
  - `teardown.py` deletes strictly by marker, with CSV audit log and typed confirmation.
  - The suite uses its own `HUBSPOT_SANDBOX_ACCESS_TOKEN` env var — a production token in `HUBSPOT_ACCESS_TOKEN` is invisible to it, and every script re-checks the account-type gate independently.
- **Mock enrichment provider** (`waterfall-enrich-contacts/scripts/providers/mock.py`) — deterministic fake data, no network, no credits; lets the enrichment pipeline be tested for free.
- **Optional CI**: `.github/workflows/sandbox-self-test.yml`, manual dispatch only, using a `HUBSPOT_SANDBOX_ACCESS_TOKEN` repository secret; uploads the report as an artifact.
- CONTRIBUTING.md gains a "Testing Your Skill" section: scripted-skill contributions extend the fixture matrix and case registry (or document why they're not sandbox-testable).

## 1.1.0 — 2026-07-12

Modernization release tracking HubSpot's 2026 platform changes.

### New skills (32 → 36)

- **`workflows-as-code`** (automation-workflows) — export all workflows to versioned JSON via the v4 Automation API's batch read, diff exports over time, restore workflows from backup (created disabled, for review).
- **`connect-hubspot-mcp`** (audit-planning) — connect Claude Code to HubSpot's official remote MCP server (GA April 2026) for conversational reads and spot-checks; documents the MCP-vs-scripts division of labor.
- **`audit-api-usage`** (audit-planning) — inventory every API caller and flag legacy v1–v4 usage ahead of HubSpot's March 30, 2027 end of support; migration checklist to date-based versions (`2026-03`).
- **`waterfall-enrich-contacts`** (data-enrichment) — external enrichment with pluggable provider adapters: FullEnrich (default), Apollo, Hunter, Dropcontact, plus a template for custom providers. Cost caps, cost preview, double typed confirmation, no-overwrite default, full audit trail.

### Workflows are API-first

HubSpot's v4 Automation API is stable (create/update/batch read, all object types, all action types; v3 is legacy). The four workflow-builder skills (`new-contact-hygiene`, `engagement-suppression`, `lifecycle-progression`, `bounce-monitoring`) now ship before/execute/after scripts that create their workflows via `POST /automation/v4/flows` — **always disabled, for UI review before enabling**. Nested-branch designs were decomposed into small linear flows. Manual UI builds remain as the fallback; Breeze AI / Chrome-extension guidance demoted to alternatives. The stale "v4 is beta/unstable — do not use" warnings are gone from every file.

### Corrections & refreshes

- **`build-lead-scoring`** rewritten around the post-August-2025 scoring tool: layered limits→groups→rules→criteria, decay, contact/company/deal scoring, and the key nuance that score *configuration* is UI-only while the generated score/threshold *properties* are API-readable.
- **`hubspot-audit`** now ships the `scripts/audit_portal.py` it always referenced (read-only, 8 dimensions, graded markdown report). The un-implementable "aggregate email open/click rate" audit items were replaced with per-contact engagement properties, with per-email rates pointed at the marketing email statistics API. New lifecycle-consistency check using the `hs_current_customer` system property (June 2026).
- **`lifecycle-progression-workflow`**'s Opportunity→Customer trigger now uses `hs_current_customer`.
- **`cleanup-workflows`** gains a scripted off-then-delete path and mandates a `/workflows-as-code` export before deletions.

### Consistency (docs now match code)

- One env var everywhere: `HUBSPOT_ACCESS_TOKEN` (docs previously said `HUBSPOT_API_TOKEN`; scripts always used the former).
- One Python house style: plain `requests` against versioned REST endpoints — all inline `hubspot-api-client` examples rewritten to match the shipped scripts.
- One uv pattern: PEP 723 inline metadata + `uv run skills/<skill>/scripts/<stage>.py`.
- Every scripted skill links its scripts in a Scripts table; stage naming unified (Plan → Before → Execute → After + required Rollback); CSV audit logs standardized to `data/audit-logs/`.
- `build-smart-lists` reconciled with its own execute script; `create-icp-tiers` docs aligned to the scripts' tier values.
- New `CONTRIBUTING.md` with the full skill spec; MCP and API-versioning documented in README and `CLAUDE.md`.

## 1.0.0 — 2026-03

Initial release: 32 skills across audit & planning, database hygiene, data enrichment, segmentation & scoring, automation workflows, and ongoing maintenance.
