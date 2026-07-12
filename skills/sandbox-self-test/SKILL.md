---
name: sandbox-self-test
description: "Verify the entire toolkit against a disposable HubSpot developer test account or sandbox that you bring: seed synthetic fixtures, run every scripted skill's read path, exercise end-to-end and API round-trip cases, produce a graded report, and tear everything down. Hard-refuses to run against production."
license: MIT
metadata:
  author: tomgranot
  version: "1.0"
  category: audit-planning
---

# Sandbox Self-Test

## Purpose

Every skill in this repo mutates or reads a live HubSpot portal, and no two portals are alike. This skill lets anyone — a contributor before opening a PR, an admin before trusting the toolkit with production, or the maintainer after a HubSpot API change — verify the whole toolkit against a **disposable portal they bring themselves**. HubSpot gives every account up to 10 free developer test accounts, so there is no shared test infrastructure to maintain and no credentials in the repo: bring your own sandbox, run the suite, read the report, throw the sandbox away.

## Key Constraint

**This suite seeds, mutates, and deletes data. It must never touch production.** The lockout is enforced in code, not by convention:

1. The suite reads its own env var, `HUBSPOT_SANDBOX_ACCESS_TOKEN` — it never reads `HUBSPOT_ACCESS_TOKEN`, so a production token in your `.env` cannot be picked up by accident.
2. Every script (not just preflight) calls `GET /account-info/v3/details` before acting and **refuses unless `accountType` is `DEVELOPER_TEST` or `SANDBOX`**. The check fails closed — any error verifying the account type is a refusal — and there is no override flag.

## Prerequisites

- A **developer test account** (free: HubSpot Settings > Testing > Developer test accounts, up to 10 per account, 90-day expiry renewed by API activity) or a **standard sandbox** (Enterprise plans)
- A private app **inside that test account** with scopes: `crm.objects.contacts.read/write`, `crm.objects.companies.read/write`, `crm.objects.owners.read`, `crm.lists.read/write`, `automation`
- Its token in `.env` as `HUBSPOT_SANDBOX_ACCESS_TOKEN` (keep it separate from your production `HUBSPOT_ACCESS_TOKEN`)
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/preflight.py`](./scripts/preflight.py) | `uv run skills/sandbox-self-test/scripts/preflight.py` |
| Execute | [`scripts/seed.py`](./scripts/seed.py) | `uv run skills/sandbox-self-test/scripts/seed.py` |
| Execute | [`scripts/run_suite.py`](./scripts/run_suite.py) | `uv run skills/sandbox-self-test/scripts/run_suite.py` |
| After | [`scripts/teardown.py`](./scripts/teardown.py) | `uv run skills/sandbox-self-test/scripts/teardown.py` |

`preflight.py` gates on account type and probes scopes. `seed.py` creates the fixture matrix (idempotent). `run_suite.py` runs the cases and writes the report (`--list` prints the plan without any API call). `teardown.py` deletes everything marker-matched, with typed confirmation.

## Execution Pattern

### Stage 1: Plan

Confirm with the user:

1. **Which portal.** They must name the developer test account / sandbox being used. If they only have a production token, stop and walk them through creating a test account first — do not improvise.
2. **What is in it.** The suite tolerates other data in the sandbox (all assertions are marker-scoped), but a sandbox that mirrors production data deserves a warning: `delete-no-email-contacts` runs for real and will delete *all* no-email contacts in the portal, not just fixtures. An empty or purpose-made sandbox is the recommendation.
3. **Whether to tear down at the end** (default: yes).

### Stage 2: Before

Run preflight. It must print `GO` — portal ID, account type, and all scope probes OK. A `REFUSED` here is the safety system working; never work around it.

### Stage 3: Execute

Seed, then run the suite:

1. `seed.py` creates 3 companies and 9 contacts, one defect per testable skill (no email, no owner, no lifecycle stage, messy geo spellings, duplicate company domains, missing company name with an association to copy from, an enrichable contact for the mock provider).
2. `run_suite.py` runs three kinds of cases:
   - **before-smoke** — every scripted skill's `before.py` runs as a subprocess with the sandbox token standing in for `HUBSPOT_ACCESS_TOKEN`; read-only, asserts clean exit. This is the widest net: it catches endpoint drift, scope gaps, and pagination breakage across the whole toolkit.
   - **end-to-end** — `delete-no-email-contacts` (full destructive cycle with piped confirmation, verified against the Search API), `waterfall-enrich-contacts` with the **mock provider** (no credits spent, write-back verified), `workflows-as-code` export (JSON on disk verified).
   - **api-roundtrip** — a dynamic list and a v4 workflow are each created (`[SELFTEST]`-prefixed, workflow disabled with a never-matching enrollment filter), fetched, verified, and deleted.

All fixtures are triple-marked: reserved-TLD emails (`@selftest.hubspot-admin-skills.invalid` — can never receive mail), `SELFTEST` name prefixes, `[SELFTEST]` list/workflow prefixes.

### Stage 4: After

Read `reports/selftest-{date}.md` with the user: PASS/FAIL/SKIP per case. Investigate any FAIL before using the failing skill on production — a failure here is either a fixture problem, a scope problem, or a real regression against HubSpot's current API behavior, and telling those apart is the whole point of the suite. Then run teardown.

## Safety Mechanisms

| Mechanism | Detail |
|-----------|--------|
| **Production lockout** | Account-type gate (`DEVELOPER_TEST`/`SANDBOX` only) enforced independently in preflight, seed, suite, and teardown. Fails closed, no override. |
| **Separate token variable** | `HUBSPOT_SANDBOX_ACCESS_TOKEN` only — a production token in `HUBSPOT_ACCESS_TOKEN` is invisible to this suite. |
| **Marker-scoped teardown** | Deletion matches selftest markers (reserved-TLD email domain, `SELFTEST`/`[SELFTEST]` prefixes) — never "everything in the portal". |
| **CSV audit trail** | Teardown exports every object it will delete to `data/audit-logs/` before deleting, and requires typed `TEARDOWN` confirmation. |
| **No credits spent** | The enrichment case forces `ENRICHMENT_PROVIDER=mock` (deterministic fake data, no network). |
| **Skips are visible** | Anything a sandbox can't simulate is reported `SKIP` with the reason — the report never overstates coverage. |

## Technical Gotchas

1. **A sandbox cannot simulate everything.** Bounce state (`hs_email_hard_bounce_reason_enum`), global unsubscribes (`hs_email_optout`), marketing status (`hs_marketable_status`, read-only via API), and deactivated owners all come from real events HubSpot records — they cannot be fabricated. The suite reports these as SKIP; verify those paths once, manually, when first running the corresponding skills on a real portal.
2. **Search index lag.** The Search API indexes writes asynchronously; the suite sleeps ~5s before asserting post-mutation counts. On a slow day a fresh mutation can still be missed — re-run the suite before concluding a skill is broken.
3. **Developer test accounts expire after 90 days** without API activity. Running this suite counts as activity, so a monthly run keeps the sandbox alive. Deleted fixtures follow the same 90-day recovery window as production.
4. **`before-smoke` failures on an empty sandbox are usually legitimate zero-data exits.** The shipped `before.py` scripts exit 0 on "nothing found" — if one exits non-zero on your sandbox, read its output in the report; that's a real signal, not noise.
5. **Plan-tier gaps.** Developer test accounts carry Enterprise-trial features, but a standard sandbox inherits its parent portal's tier — the v4 workflow round-trip reports SKIP on 403 rather than failing.

## Rollback

Teardown *is* the rollback: `uv run skills/sandbox-self-test/scripts/teardown.py` removes every marker-matched object, and archived records remain recoverable in the sandbox for 90 days (Settings > Data Management > Deleted Objects). The nuclear option is equally valid: delete the developer test account and create a fresh one — that is what "disposable" means. Nothing this skill does can touch production, by construction.

## CI (optional)

A ready-made GitHub Actions workflow ships at [`ci/sandbox-self-test.yml`](./ci/sandbox-self-test.yml). To enable it, copy it into your fork's workflows directory and set the repository secret:

```bash
mkdir -p .github/workflows
cp skills/sandbox-self-test/ci/sandbox-self-test.yml .github/workflows/
gh secret set HUBSPOT_SANDBOX_ACCESS_TOKEN
```

It runs preflight → seed → suite → teardown on **manual dispatch only** and uploads the report as an artifact. It never runs on push or PR — the sandbox is yours, so the trigger is too. (It ships outside `.github/workflows/` deliberately: enabling CI that spends your sandbox is an explicit opt-in, and tokens without the `workflow` scope can still push this repo.)
