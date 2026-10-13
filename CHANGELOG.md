# Changelog

## Unreleased

### `cleanup-deals` gets scripted stages

The sales audit routes most of its findings to `cleanup-deals`, which until now was instructions only.

- **`scripts/before.py`** (read-only) exports one CSV per finding: open deals past their close date, open deals with no logged activity in N days (`--stale-days`, default 60), open deals missing amount or close date, closed-lost deals with no loss reason, and likely test deals. Salesforce-synced deals are skipped and counted.
- **`scripts/execute.py`** is deliberately conservative. By default it creates one review task per deal owner listing their flagged deals; it never closes deals or edits deal properties. With `--delete-from-csv` it deletes only test deals a person marked `yes` in the reviewed CSV, refusing Salesforce-synced and closed-won deals. Abort thresholds, a CSV written before any write, and typed confirmation in both modes.
- **`scripts/after.py`** re-counts every finding and prints a before/after comparison.
- These are the first scripts to target the date-based API version `2026-09`. They are covered by an offline suite (`tests/test_cleanup_deals.py`) and **have not been run against a live portal**.

## 2.0.0 — 2026-10-12

Two audiences on one engine, and a full pass over everything HubSpot and Claude Code changed since 1.2.

### Marketing and sales audits (37 → 40 skills)

- **`hubspot-audit`** is now one engine with three scopes. `scripts/audit_portal.py --scope full|marketing|sales` tags every dimension as shared, marketing, or sales. The shared dimensions (database size, owner health, company data, duplicates) run under every scope, so the scoped reports agree on what they have in common.
- **`hubspot-sales-audit`** (new, audit-planning): pipeline configuration, deal data quality, pipeline hygiene and velocity, sales ownership and handoff, activity and follow-up.
- **`hubspot-marketing-audit`** (new, audit-planning): deliverability, contact completeness, engagement, and list, workflow, and form health.
- Every finding names its fix skill, and the report opens with a generated, prioritized prescription. A JSON twin is written beside the markdown.
- Unreadable objects (missing scope, hub not purchased) report `n/a` and grade `?` instead of a false zero.
- Workflows, forms, and deactivated owners are fully paginated. Pacing stays under the Search API limit of 5 requests per second.
- **`hubspot-implementation-plan`** reads any of the three reports, plans only what the report measured, and gains a sales pipeline track.

**Breaking:** the full report's section numbering and layout changed, and `audit_portal.py` now requires `HUBSPOT_ACCESS_TOKEN` at startup rather than failing on first request. Report filenames for the full scope are unchanged.

### Connections

- **`connect-hubspot-agent-cli`** (new, audit-planning): HubSpot's Agent CLI (public beta, June 2026), the direct connection for Claude Code. Install, user versus service key mode, command surface, safe-use rules.
- **`connect-hubspot-mcp`** rewritten. HubSpot's remote MCP server has no dynamic client registration, so the previous `claude mcp add` command could not authenticate. Setup now goes through an MCP connector. The skill lists the server's tools with their documented limits and states what it cannot do: delete or archive, workflows, property updates.

### HubSpot platform changes

- **Service keys replace private apps.** HubSpot disables creating legacy private apps on 2026-10-26 (2026-09-28 for new accounts). Prerequisites across all skills now ask for a service key; existing private app tokens still work.
- **API versions.** Current date-based version is `2026-09`. v4 support ends 2027-03-30. v1–v3 are unsupported since 2026-09-15, with enforcement in September 2027. `audit-api-usage` is rewritten around the two cutoffs and treats legacy private apps as their own migration item.
- **Rate limits** corrected from a flat 100 per 10 seconds to the per-tier figures (100 Free/Starter, 190 Professional/Enterprise, per app), plus the Search API's separate 5 per second.
- **Workflows API is beta.** 1.1 described the v4 Automation API as stable. HubSpot documents it as beta, with its reference at `/automation/v4/2027-03-beta/flows`. The workflow skills now say so, and document that `PUT` requires the current `revisionId`, drops omitted fields, and that deleted workflows are not restorable through the API.
- **`build-lead-scoring`** documents the beta Lead Scoring API (`/marketing/lead-scoring/2027-03-beta/scores`).

### Claude Code plugin conventions

- **Script paths are relative to each skill** (`scripts/before.py`, `../hubspot-audit/scripts/audit_portal.py`). The previous repo-relative paths did not exist when the skills were installed as a plugin.
- Plugin manifest gains author, homepage, repository, license, and keywords. `claude plugin validate .` is a documented pre-PR step.

### Tests

- New offline test suite for the audit engine (`tests/`), run in CI on every pull request. A fake HubSpot answers every request with synthetic counts: no token, no portal.

### Site

- Homepage presents the three audits. Three new problem pages. Platform facts corrected throughout.

### Known gaps

- **Script endpoints still target `/crm/v3/`, `/marketing/v3/`, and `/automation/v4/`.** Migration to date-based paths is deferred to per-skill changes verified through `/sandbox-self-test`, because HubSpot states that not every v3 contract carries over and `2026-09` rejects writes that omit admin-required properties.
- **The new sales dimensions have not been run against a live portal.** They are covered by the offline suite and degrade to `n/a` when a property or object is unreadable. Run `/sandbox-self-test` and a sales-scoped audit on a developer test account before relying on them.
- **The Claude Code MCP setup steps are derived, not published.** HubSpot documents the connector flow but not Claude Code specifically.
- **Sales-side fix skills are thin.** Most sales findings route to `cleanup-deals`, which has no scripts yet.

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
- **Optional CI**: a ready-made workflow at `skills/sandbox-self-test/ci/sandbox-self-test.yml` (copy into `.github/workflows/` to enable) — manual dispatch only, using a `HUBSPOT_SANDBOX_ACCESS_TOKEN` repository secret; uploads the report as an artifact.
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
