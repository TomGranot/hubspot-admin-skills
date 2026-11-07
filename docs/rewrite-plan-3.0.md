# HubSpot Admin Skills 3.0: Rewrite and Expansion Plan

**Status:** proposal, 2026-11-07
**Scope:** the audit engine, the skill catalog, the script layer, the platform migration, and the quality bar that gates all of it

---

## 1. Why a rewrite

2.0 shipped a decent idea (one read-only engine, three lenses, a prescription that names skills) on a thin implementation. The feedback since then clusters into three complaints, and each traces to a design choice rather than a bug:

| Complaint | Root cause in 2.0 |
|---|---|
| **"The checks are not complete enough."** | The engine runs about 45 Search API `total` counts over contacts, companies, deals, tasks, leads, plus three list/workflow/form inventories. It never paginates records, so anything that needs to look at a record (duplicates, bad values, invalid formats, distributions) is "flagged, not counted". Issue #1 is exactly this: HubSpot's native duplicate tool found far more than the audit, because the audit did not look. |
| **"A lot of what people use HubSpot marketing and sales for is not covered."** | Coverage is limited to CRM record hygiene. Nothing on marketing email performance, campaigns, forms conversion, landing pages, ads, lead scoring health, lifecycle funnel conversion, consent and subscription types, or the marketing contact tier. Nothing on sequences, meetings, calls, logged emails, quotes, products, line items, forecasts, playbooks, or rep activity. Nothing at all on Service Hub, Commerce, custom objects, users and permissions, integrations, or the data model itself. |
| **"The results and recommendations are not good enough."** | Each dimension is graded on one proxy metric (Contact Completeness grades only on `lifecyclestage`, so a portal missing company, industry, country, and job title on 60% of contacts gets an A). Findings are bare counts with no samples, no breakdown by source, owner, pipeline, or create date, no trend against the last run, and no expected impact. The "recommendation" is the name of a skill. The implementation plan is a static template with invented hour estimates. Twelve of the prescribed skills have no scripts, so following the prescription lands on a checklist. |

A fourth, quieter problem: the platform moved. Every script except `cleanup-deals` still calls `/crm/v3/`, `/automation/v4/`, `/marketing/v3/`. The 2026-09 API version now enforces admin-configured validation on writes (400 on a missing conditionally-required property), so `execute.py` scripts that worked in the spring will start failing in portals with validation rules. HubSpot has shipped a public Sequences API, a Property Validations API, an Object Tags API, merge rules in the Data Quality tool, the Agent CLI (public beta) with its own skills package, and a Breeze Assistant that can now take action. The toolkit should know about all of it.

### Goals for 3.0

1. **Evidence, not counts.** Every finding carries sample records, a breakdown, a confidence, a root-cause hypothesis, an impact statement, and a fix (skill or UI steps). A grade is never computed from a single metric.
2. **Cover what admins actually run HubSpot for.** Marketing performance and consent, sales activity and enablement, service, commerce, the data model, governance. Six lenses instead of three.
3. **Honest coverage.** The report states what it checked, what it could not check and why (scope, hub, tier, no API), and how to get the missing data.
4. **Every prescribed skill is runnable.** No skill appears in a prescription unless it ships at least a `before.py`.
5. **Current platform.** `2026-09` everywhere, validation-aware writes, the new APIs, the Agent CLI as an optional backend.
6. **Proven, not asserted.** A seeded sandbox with known defects, and the audit must find every one of them before a release ships.

### Non-goals

- Rebuilding HubSpot's UI-only tools (duplicate management UI, email health dashboard). Where HubSpot has the better tool, the report says so and links the user to it.
- Per-rep performance scoring. Activity *data quality* is in scope; ranking people is not.
- Supporting v1-v3 endpoints in new code.

---

## 2. Architecture

### 2.1 Shared library

Today every script re-implements auth, pagination, retry, CSV writing, and the `.env` lookup. `cleanup-deals` already broke the pattern with a sibling module (`deal_findings.py`) and it is the best-tested skill in the repo. Generalize that.

```
lib/hubspot_admin/            # one package, imported by every script
  client.py                   # auth (service key), versioned paths, retry, rate-limit pacing per tier, warnings[] surfacing
  search.py                   # count(), scan() with >10k segmentation, filter builders
  scan.py                     # full-record pagination into a local JSONL cache, resumable
  validation.py               # read Property Validations + property definitions; preflight a write payload
  findings.py                 # Check, Finding, Evidence, Severity, Coverage models
  report.py                   # markdown + JSON renderers, history diff
  sandbox.py                  # account-type gate (moved from sandbox-self-test, used by every execute.py)
  csvlog.py                   # audit-trail writer
```

Scripts stay single-file `uv run` entry points with PEP 723 metadata. They reach the library with one line at the top (resolve `lib/` relative to `__file__`, which works from a clone and from the plugin cache, exactly as `../hubspot-audit/scripts/...` already does). Publishing the package to PyPI so scripts can declare it as a PEP 723 dependency is a later option, not a 3.0 requirement.

**Decision needed:** `lib/` at the repo root (cleanest) vs. `skills/hubspot-audit/scripts/lib/` (keeps everything under `skills/`). Root is recommended; `claude plugin validate` does not care about non-skill directories, and the site build walks up from `site/` already.

### 2.2 Check model

Replace `Dimension.add(metric, count, skill)` with declarative checks:

```python
@check(
    id="contacts.duplicates.email_exact",
    lens="shared", hubs=(), scopes=("crm.objects.contacts.read",),
    title="Contacts sharing an email address",
    fix="merge-duplicate-contacts",
    impact="Double counts in reports, split engagement history, duplicate sends.",
)
def contact_email_duplicates(ctx) -> Finding:
    ...
```

A `Finding` has: `count`, `denominator`, `share`, `severity` (0-4, computed from share × impact weight × confidence), `evidence` (up to N sample record IDs with the properties that triggered the finding, plus a HubSpot deep link), `breakdown` (by source, owner, pipeline, create-month, whichever is relevant), `root_causes` (ranked hypotheses the check can test: e.g. "72% of no-email contacts came from the Salesforce sync"), `fix` (skill slug, or UI steps when no API exists), `coverage` (`ran`, `skipped:no_scope`, `skipped:no_hub`, `skipped:no_api`, `partial:10k_cap`).

Dimension grade = worst finding severity in the dimension, adjusted by how much of the dimension actually ran. A dimension with three skipped checks cannot grade above B and says why. This directly fixes the Grade-A-that-was-F complaint.

### 2.3 Record scan layer

The single biggest capability gap. `scan.py` paginates full records (Search API, 200 per page, segmented by `createdate` ranges when a query exceeds the 10,000-result cap; sorted by `hs_object_id` as a fallback) into a local JSONL cache under `data/cache/` (gitignored, PII). Checks that need records (duplicates, format validation, value distributions, association gaps) read the cache; a run reuses a cache younger than the configured TTL. For portals above roughly 500k contacts, the scan offers two alternatives: the Agent CLI's bulk export, or HubSpot's CRM export API, both producing the same JSONL.

### 2.4 History and trends

Every run writes `reports/history/{scope}-{date}.json` (versioned schema). The renderer diffs against the previous run: new findings, resolved findings, counts up or down, grade changes. The weekly and quarterly skills become "run the audit, read the diff" instead of "open these dashboards".

### 2.5 Backends

Three ways to reach the portal, one interface:

| Backend | Use | Status |
|---|---|---|
| REST via service key (default) | Everything scripted | Service keys are public beta but the only path HubSpot is building for account-level access |
| HubSpot Agent CLI (`hubspot …`) | Bulk export/import, long-tail admin jobs, user-mode auth where a service key cannot (sequences enrollment is user-scoped) | Public beta since 2026-06-23; commands may change |
| HubSpot MCP server | Spot-checks, opening sample records from a finding | GA |

The library gets a `backend` option so a scan can run through the CLI when the user has it installed; the REST path remains the reference implementation.

---

## 3. Check catalog: what 3.0 audits

Six lenses. **Shared** runs under every scope. The marketing and sales lenses keep their 2.0 checks and grow. Service, commerce, and platform are new. Each row names the data source and whether 2.0 had it.

### 3.1 Shared (CRM foundation)

| Check | Source | 2.0 |
|---|---|---|
| Database size, growth per month (last 12), marketing vs non-marketing split, **marketing contact tier utilization** (billed tier vs used) | Search counts by `createdate` buckets; `hs_marketable_status`; account info API for tier | size only |
| **Duplicate contacts**: exact email, normalized email (plus-addressing, case, dots in gmail), same phone, same first+last+company | record scan | not counted |
| **Duplicate companies**: same domain, normalized domain (www, subdomains), fuzzy name within same country | record scan | before.py only |
| Contacts with no associated company although email domain matches an existing company | record scan + companies by domain | no |
| Companies with no contacts; contacts with no company (B2B portals) | Search `num_associated_contacts` / companies | no |
| Owner health: unowned, deactivated owners, **owner load distribution** (Gini across active owners), owners with zero records | owners API + per-owner counts | partial |
| Invalid values: emails failing syntax, phones not E.164-normalizable, URLs not URLs, dates in the future where they cannot be | record scan | no |
| Picklist drift: free-text industry/country/state values that do not match the property's options or ISO lists | record scan + property definitions | no |
| Required-but-empty: properties the admin marked required (Property Validations API, conditionally required rules) that are empty on existing records | validations API + counts | no |
| Properties: total per object, custom properties with 0 or <1% fill, duplicate-meaning properties (name similarity + value overlap), properties not used in any list/workflow/report (where readable) | properties API + record scan | prose only |
| Associations: records with no associations at all; association labels defined but unused | associations API | no |
| Lifecycle funnel: counts per stage, **stage order violations** (customer with no closed-won deal, opportunity with no deal, SQL never owned), stage distribution vs create cohort | counts | partial |
| Deleted/restorable records in the recycle window (contacts, companies, deals deleted in the last 90 days, by who) | not available by API: report as `no_api` with UI path | no |

### 3.2 Marketing

| Check | Source | 2.0 |
|---|---|---|
| Deliverability: hard bounces, global unsubscribes, 3+ bounces, never emailed, **bounce rate trend**, **spam reports**, **unsubscribe rate** over the last 90 days | contact properties + marketing email statistics | partial |
| **Marketing email performance**: sends, delivered, open, click, unsubscribe, spam per email for the last 90 days; emails under portal median; emails with zero clicks; sends to lists with >10% suppressed | `/marketing/v3/emails/statistics/list` (verify the 2026-09 path exists; v3 is unsupported from Sept 2027) | no |
| **Subscription types and consent**: subscription types defined, contacts with no subscription status, legal basis missing on GDPR-enabled portals, double opt-in state | subscription preferences API + contact properties | no |
| Lists: total, active vs static, **lists with 0 members**, lists not updated in 180 days, lists not used by any workflow or email (where readable), lists over the processing limit | Lists API (`2026-09`) + flow/email references | count only |
| Forms: total, **forms with 0 submissions in 90 days**, forms creating contacts with no lifecycle stage, forms without consent fields on GDPR portals, submission volume trend, spam share (free-mail + gibberish names) | Forms API + submissions + record scan by `hs_analytics_source` | count only |
| Landing pages and CTAs: pages with 0 views, pages with forms that never convert, unpublished drafts older than 180 days | CMS pages API, CTAs API | no |
| Campaigns: campaigns with no assets, no contacts, no budget, no end date; campaign attribution availability | Campaigns API | no |
| Workflows: total, active, **never enrolled anything**, no enrollments in 90 days, turned off 90+ days, **error state**, workflows referencing deleted properties or lists, test-named workflows, unfolder'd sprawl | Flows API (beta) + enrollment where readable; UI-only metrics reported as `no_api` | count only |
| Lead scoring: score properties present, **score distribution** (how many contacts have a non-zero score, percentile spread), scores never used by a list or workflow, MQL threshold vs actual MQL count | Lead Scoring API (beta) + counts | no |
| Lifecycle conversion: MQL→SQL→Opportunity→Customer conversion over the last two quarters; stage velocity where date-entered properties exist | `hs_date_entered_*` properties | no |
| Source attribution quality: contacts with `hs_analytics_source` offline/unknown share, UTM-less paid traffic | counts | no |
| Ads: connected ad accounts, campaigns with spend and no leads (where the Ads API is readable) | Ads API (verify current state) | no |
| Email sending domains, DKIM/DMARC, tracking code installed | `no_api`: report with UI path | no |

### 3.3 Sales

| Check | Source | 2.0 |
|---|---|---|
| Pipeline config, deal data quality, stale/past-due deals, win rate, orphaned deals, SQL/Opportunity ownership, overdue tasks, leads | existing checks, migrated | yes |
| **Deal stage probability sanity**: stages whose actual win rate differs from configured probability by >20 points | pipelines + closed deal counts per stage | no |
| **Time in stage**: open deals above the 90th percentile of time in current stage (`hs_date_entered_<stage>`, `hs_v2_date_entered_*`) | deal scan | no |
| **Stage skipping and backward movement** counts (where `hs_v2_date_exited_*` is available) | deal scan | no |
| Deals with amount outliers (10× the pipeline median), deals with amount in the wrong currency on multi-currency portals | deal scan | no |
| Deals with no line items on portals that use products; products never used | line items, products | no |
| **Activity capture**: open deals and SQL+ contacts with no logged call/email/meeting in N days (activity objects, not `notes_last_updated`), owners with zero logged activity in 30 days | calls, emails, meetings objects via Search | partial |
| **Sequences**: total, active, **reply rate and bounce rate per sequence**, sequences not used in 90 days, enrollments of contacts who are unsubscribed or bounced | Sequences API (public, `2026-09`; some endpoints user-scoped: fall back to Agent CLI user mode) | no |
| Meetings: meeting links active, meetings booked last 90 days, no-show rate where recorded | Meetings API | no |
| Tasks: overdue, tasks with no due date, tasks assigned to deactivated users, tasks older than 180 days still open | tasks object | partial |
| Quotes: open quotes past expiry, quotes on closed deals, quote templates unused | Quotes API (`2026-09`) | no |
| Forecast: forecast submissions missing for the current period per owner (Sales Hub Pro+) | forecasts API | no |
| Goals: owners with no goals set | goals API | no |
| Playbooks and snippets: unused in 180 days | `no_api` or UI | no |
| Object tags on deals: tags defined but unused | Object Tags API (`2026-09`, new GA) | no |

### 3.4 Service (new lens)

| Check | Source |
|---|---|
| Ticket pipelines: pipelines with 0 tickets, >10 open stages, tickets with no owner, no priority, no category, no associated contact |
| Open tickets with no activity in N days; tickets open >30 days; tickets closed with no resolution |
| SLA: tickets breaching time-to-first-response / time-to-close where SLA properties exist |
| Feedback: NPS/CSAT survey response volume and trend; surveys with 0 responses (`feedback_submissions`, read-only) |
| Conversations inbox: channels connected, unassigned conversations older than 24h (Conversations API) |
| Knowledge base: articles with 0 views (where readable) |
| Customer Agent: enabled, resolution rate (`no_api` unless surfaced) |

### 3.5 Commerce (new lens, optional)

Products with no price, line items with 0 amount, invoices overdue, subscriptions with failed payments, quotes without payment links. Only runs when the portal has the objects. Smallest lens; gated behind a flag until there is demand.

### 3.6 Platform and governance (new lens)

| Check | Source |
|---|---|
| Users: total, seats by type, **users inactive 90+ days**, users with Super Admin, deactivated users still owning records, users without a team | Users API + owners |
| Teams: teams with no members, records assigned to no team on team-partitioned portals | teams API |
| Integrations: connected apps, apps with no API activity in 90 days, legacy private apps still in use, integrations on v1-v3 or v4 endpoints (merges `audit-api-usage`) | account/apps APIs + API usage |
| Validation rules: objects with no required properties, pipelines with no stage-required properties, conditionally-required rules the data violates | Property Validations API |
| Data model: custom objects, custom object record counts, custom objects with 0 records, association definitions unused | schemas API |
| API usage vs daily limit, Search API throttling observed during the run | account API usage endpoints |
| Credits: Breeze/agent credit consumption and feature caps (where readable) | `no_api` otherwise |
| Sandbox hygiene: developer test accounts count, age | account info |
| Audit log availability (Enterprise): recent property definition deletions, workflow deletions | audit log API where present |

Target: roughly 110 checks across the six lenses, up from about 45 metrics.

---

## 4. Report and recommendations

### 4.1 Report structure

```
# HubSpot Portal Audit — {portal name}, {date}

## Summary
Three paragraphs written from the findings: the biggest problem, the second, what is healthy.
Coverage line: "Ran 94 of 112 checks. 11 skipped (no Service Hub), 7 skipped (token lacks scopes: ...)."
Change since {last run}: 3 new findings, 2 resolved, Deal Data Quality C → B.

## Top findings (max 7)
Each: severity, count and share, one-sentence impact, root cause with evidence, fix.

## Prescription
Ordered skills with the finding that triggered each, expected effect on the grade, dependency notes.

## Lens sections
Per finding: count | share | trend | severity, then:
  Evidence: 5 sample records (deep links), breakdown table.
  Why this happens: ranked hypotheses the check tested.
  Fix: `/skill` or numbered UI steps. Prevention: validation rule / workflow / setting.

## What this audit could not check
Table: check, reason (scope / hub / tier / no API), how to get it (UI path or scope to add).

## Method
Thresholds used, API version, run time, request count.
```

### 4.2 Recommendation quality

- **Root-cause tests, not guesses.** Each check can declare `breakdown_by` (`hs_analytics_source`, `hs_object_source`, `hubspot_owner_id`, `pipeline`, create-month). The renderer reports the top contributor only when it explains >40% of the finding.
- **Impact in the portal's own numbers.** "4,120 unreachable contacts are 19% of your marketing contact tier; dropping them moves you under the 20,000 tier boundary." "Deals with no amount hide an estimated $X from the weighted pipeline" (median amount × count, labeled as an estimate).
- **Benchmarks, labeled.** A small, editable table of reference ranges (bounce rate under 2%, open rate 20-35% B2B, etc.) with sources, in `lib/hubspot_admin/benchmarks.py`. The report says "above the typical range" rather than "bad".
- **Prevention beside every cleanup.** Each finding maps to the HubSpot setting, validation rule, or workflow that stops it recurring. 2.0 says this in prose for sales; make it a field on the check.
- **Implementation plan generated, not templated.** `/hubspot-implementation-plan` reads the JSON and emits only triggered tasks, sequences them from the dependency field on each skill's frontmatter, and estimates effort from record counts and a per-skill throughput constant instead of a fixed "1-2 hrs".

---

## 5. Skill catalog changes

### 5.1 Scripts for every prescribed skill

Twelve skills are prose-only today. Minimum bar: `before.py` that produces the finding CSV the audit already computed, so the prescription leads somewhere. Where a safe write exists, add `execute.py` under the standard safety table.

| Skill | 3.0 scripts |
|---|---|
| cleanup-lists | before (inventory + 0-member + unused), execute (delete static lists marked `yes` in the reviewed CSV) |
| cleanup-forms | before (inventory + submissions + conversion), execute (archive forms marked `yes`) |
| cleanup-workflows | before (inventory + enrollment + errors + references), execute (turn off marked workflows; delete only after a `workflows-as-code` export exists) |
| cleanup-properties | before (fill rates, duplicates, references), execute (archive marked properties) |
| cleanup-dashboards | before (dashboards + reports inventory via Reports API where readable), no execute |
| cleanup-lead-owners | before (owner load, unowned by object), execute (round-robin or rule-based reassignment, shares code with assign-unowned-contacts) |
| review-bounced-contacts | before (3+ bounces with reasons), execute (flag property for the suppression workflow) |
| backfill-geo-data | before, execute (from company, then IP-derived properties) |
| create-segment-lists | execute (Lists API `2026-09`), after |
| build-lead-scoring | before (score distribution snapshot via Lead Scoring API), after |
| audit-api-usage | folded into the platform lens; the skill becomes the migration guide |
| weekly-cleanup-routine, quarterly-database-cleanup | thin wrappers: run the audit, print the diff, run the scheduled subset |

### 5.2 New skills

**Marketing**

- `merge-duplicate-contacts`: the missing twin of the companies skill; exact and normalized email, phone, name+company; merge via API with the survivor chosen by HubSpot's merge rules when the portal defines them
- `audit-email-performance`: per-email and per-list performance, worst performers, suppression leakage
- `cleanup-subscription-types`: consent and subscription type hygiene; legal basis backfill plan on GDPR portals
- `cleanup-campaigns`: empty and stale campaigns
- `cleanup-landing-pages`: zero-view pages, non-converting forms, stale drafts
- `audit-lead-scoring`: distribution, dead scores, threshold calibration against actual MQL→SQL conversion
- `build-lifecycle-funnel-report`: date-entered based conversion and velocity, as a saved report plus CSV

**Sales**

- `audit-sequences`: performance and hygiene; unsubscribed/bounced enrollments
- `cleanup-stale-tasks`: close or reassign old open tasks (execute with threshold and typed confirmation)
- `audit-activity-capture`: who logs what, where calls and emails are missing; feeds the "stale is a logging problem" judgment
- `calibrate-stage-probabilities`: configured probability vs real win rate per stage, with the UI change list
- `cleanup-quotes`: expired open quotes, quotes on closed deals
- `set-stage-required-properties`: writes the prevention (Property Validations API) the sales audit keeps recommending in prose

**Service**

- `hubspot-service-audit`: the lens entry point
- `cleanup-tickets`: stale, unowned, uncategorized tickets; review tasks per owner
- `audit-sla-breaches`

**Platform**

- `hubspot-platform-audit`: the lens entry point (users, seats, integrations, validation, data model, API usage)
- `cleanup-users-and-seats`: inactive users, excess Super Admins, seat reclamation list
- `audit-validation-rules`: what is required where, what the data violates, suggested rules
- `migrate-to-date-based-apis`: the hands-on companion to `audit-api-usage`

**Infrastructure**

- `hubspot-audit` keeps its name as the full-scope entry point; `--scope` gains `service`, `platform`, `commerce`, and accepts several (`--scope marketing,sales`)
- `connect-hubspot-agent-cli` documents coexistence with HubSpot's own `agent-cli-skills` package (theirs: generic CRM operations; ours: audited, staged, rollback-able admin procedures) and the user-mode fallback for user-scoped APIs

Net: 40 → roughly 60 skills.

### 5.3 Categories

Add `service-hub` and `platform-governance`. Rename `ongoing-maintenance` to keep it, but move the `cleanup-*` skills to the lens they serve (lists, forms, campaigns to marketing; deals, tasks, quotes to sales) so the site and the prescription agree on where things live. `site/src/data/categories.ts` and the content schema change together.

---

## 6. Platform migration

| Item | Action |
|---|---|
| Date-based paths | Every script to `2026-09` (`/crm/objects/2026-09/...`, `/crm/property-validations/2026-09/...`, `/marketing/emails/2026-09/...`, `/automation/sequences/2026-09/...`). `client.py` owns the version constant; scripts never spell a path version. |
| Write validation (breaking, enforced since 2026-09-08) | `validation.preflight(object, payload)` reads the object's property definitions and validation rules once per run and reports which writes would 400 before any write is attempted. `execute.py` scripts run preflight on the first batch and stop with a readable explanation instead of a wall of 400s. Surface the new `warnings[]` array on datetime normalization. |
| v1 Pipelines sunset 2026-12-04, v4 unsupported 2027-03-30, v1-v3 enforcement 2027-09 | `audit-api-usage` dates updated; the platform lens flags integrations on each. |
| Workflows API beta path | Keep `/automation/v4/...` (beta, documented at `2027-03-beta`) with the revisionId handling; track GA. |
| Sequences API | New; confirm which endpoints accept a service key vs user token; document the Agent CLI user-mode path for the rest. |
| Property Validations, Object Tags, Notetaker recap, Merge Rules | Property Validations and Object Tags: use. Notetaker recap: optional activity-capture signal on portals that record calls. Merge Rules: read when choosing a merge survivor; document that HubSpot's planned automated bulk merge will use them, so the skill should not fight them. |
| Service keys (public beta) | Keep as default; keep the "existing private app token still works" note; add a `platform` check that lists legacy private apps still active. |
| Agent CLI | Optional backend (section 2.5). Pin a minimum CLI version in the skill and detect it at runtime. |
| Breeze Assistant / Agent Hub / Context Home | Not an API surface for us. One README section on how the toolkit relates: Breeze acts inside the portal on one task at a time; these skills run repeatable, audited, cross-object procedures with a CSV trail and rollback. Mention credit consumption as a reason admins want deterministic scripts for bulk work. |
| Rate limits | `client.py` reads the tier from account info and sets pacing; Search API pacing stays at 5 rps. |

Facts to re-verify before coding (this plan was written without direct access to developers.hubspot.com; searches summarized the pages): the `2026-09` path of the marketing email statistics endpoint; Sequences API scope and auth mode per endpoint; Ads API status; whether forms submission counts are in the Forms API or only in analytics; Users/Teams API availability per tier.

---

## 7. Quality bar

### 7.1 Seeded-defect sandbox (the acceptance test)

Extend `sandbox-self-test/seed.py` into a **golden portal**: one or more planted instances of every defect the audit claims to detect, with the expected count recorded in a manifest. `run_suite.py` runs the full audit against it and fails if any check misses its planted defects or reports extras. This is the release gate: **no 3.0 build ships until recall on the golden portal is 100%.** Issue #1 would have been caught here.

### 7.2 Offline tests

Keep the fake-HubSpot pattern, but move it into `tests/fake_hubspot.py` with recorded fixtures (anonymized JSON responses captured from a developer test account) so checks are tested against real response shapes, not hand-built dicts. One test file per lens; one for the renderer (snapshot the markdown).

### 7.3 Live validation on real portals

Before 3.0 is tagged, run the audit on at least three real portals of different shapes (small Starter, mid Professional with Sales + Marketing, large Enterprise with Service) with the owners' consent, compare each finding against what the portal's admin knows, and fix every disagreement. Record the outcome in the changelog, as 2.0 did for its gaps. This is the only answer to "the results are not good enough."

### 7.4 Field accuracy

Every finding that uses a threshold prints the threshold. Every estimate is labeled an estimate. Every `no_api` row names the UI path. No metric is reported as 0 when it was unreadable (already true, keep it).

---

## 8. Phasing

Each phase ends in a releasable state. Effort is engineering time for one person familiar with the repo.

| Phase | Deliverable | Effort | Depends on |
|---|---|---|---|
| **0. Verify and design** | Confirm the API facts in section 6 against the live docs; run the current audit on 2-3 real portals and log every miss; finalize the check catalog and the Finding schema; decide `lib/` placement | 1 week | consent from portal owners |
| **1. Core engine** | `lib/hubspot_admin/`; check model; record scan with 10k segmentation; duplicates (contacts and companies, counted); evidence and breakdowns; new renderer; history diff; golden-portal seed for the shared lens. Ship as **3.0-alpha** with the three existing scopes | 3 weeks | 0 |
| **2. Marketing expansion** | Section 3.2 checks; `merge-duplicate-contacts`, `audit-email-performance`, `cleanup-subscription-types`, `audit-lead-scoring`; scripts for cleanup-lists/forms/workflows; golden seeds | 3 weeks | 1 |
| **3. Sales expansion** | Section 3.3 checks; sequences, activity capture, time-in-stage, stage calibration, stale tasks, quotes; `set-stage-required-properties`; golden seeds | 3 weeks | 1 (parallel with 2) |
| **4. Service and platform lenses** | Sections 3.4 and 3.6; entry-point skills; users/seats, validation rules, integrations; `audit-api-usage` folded in | 2 weeks | 1 |
| **5. Migration and writes** | Every script on `2026-09` through `client.py`; validation preflight in every `execute.py`; Agent CLI backend; sandbox gate in the library | 2 weeks | 1 (can start during 2-3) |
| **6. Plan generator, docs, site** | Generated implementation plan; README, CONTRIBUTING (check authoring guide), CHANGELOG; categories, problem pages for the new skills; `skills.json` schema bump | 1.5 weeks | 2-5 |
| **7. Live validation and release** | Three-portal validation (7.3), fixes, 3.0.0 tag | 1.5 weeks | all |

Total: roughly 17 weeks sequential, about 11-12 with phases 2 and 3 in parallel. Commerce lens deferred to 3.1 unless a user asks.

Suggested cut if the timeline must shrink: ship 3.0 with phases 0, 1, 2, 3, 5, 7 (the two complaints that cost the most trust are duplicates and the thin grading, both in phase 1) and release service/platform as 3.1.

---

## 9. Breaking changes and compatibility

- Report layout and JSON schema change. `schema_version: 3` in the JSON; the plan generator refuses older files with a clear message.
- `audit_portal.py` moves to `skills/hubspot-audit/scripts/audit.py` with `--scope` accepting a list; keep `audit_portal.py` as a one-release shim that prints the new command.
- Category slugs change for moved skills: site redirects from old category pages.
- `data/cache/` added to `.gitignore`.
- Python 3.10 stays the floor.

---

## 10. Decisions needed from the maintainer

1. `lib/` at the repo root, or under `skills/hubspot-audit/`? (Recommend root.)
2. Ship service and platform lenses in 3.0 or 3.1? (Recommend 3.0 if the timeline allows; they are where "what people use HubSpot for" is least covered.)
3. Agent CLI as an optional backend in 3.0, or documentation-only until the CLI leaves beta? (Recommend optional backend, feature-flagged.)
4. Which three portals can be used for live validation, and who signs off on each?
5. Keep the "offer to create a missing skill and open a PR" flow in the audit skill? It has produced no PRs; the check-authoring guide in CONTRIBUTING may serve better.
6. Benchmarks table: include with sources, or leave relative language only? (Recommend include, clearly labeled.)

---

## Appendix A: 2.0 engine inventory (what exists today)

Thirteen dimensions, about 45 metrics, all Search API `total` counts except three list endpoints (owners, pipelines, flows/forms/lists inventory). Graded metric per dimension: owner health (unowned + orphaned), company data (missing domain only), deliverability (hard bounce + optout), contact completeness (lifecycle stage only), engagement (never opened only), pipeline config (empty + bloated), deal data (missing amount + close date), velocity (stale + past due), ownership (orphaned deals + unowned SQL/Opp), activity (overdue tasks). Duplicates, marketing assets, database size: not graded. Scripts: 24 of 40 skills ship at least one script; 1 of 24 (cleanup-deals) targets `2026-09`.

## Appendix B: Sources consulted

HubSpot developer changelog and docs (via search summaries; the sites were not reachable from this session): date-based versioning overview, 2026-09 CRM write validation enforcement, Fall 2026 Spotlight developer updates, v4 deprecation notice, Service Keys public beta, Agent CLI public beta announcement, Sequences API reference, Marketing Emails and Campaigns API guides, Property Validations API guide, Object Tags (Fall 2026), Marketing email statistics endpoint. Third-party: UNBOUND 2026 recaps (Agent Hub, Breeze Assistant, Context Home, credits), Data Quality tool merge rules (August 2026), HubSpot Community thread confirming no API for the potential-duplicates list. Repository: issue #1, CHANGELOG 2.0.0 known gaps, the engine source.
