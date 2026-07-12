---
name: waterfall-enrich-contacts
description: "Enrich HubSpot contacts (email, phone, job title) through an external enrichment provider and write results back safely. Pluggable provider adapters with FullEnrich waterfall enrichment as the default; Apollo, Hunter, and Dropcontact included; bring your own via a template."
license: MIT
metadata:
  author: tomgranot
  version: "1.1"
  category: data-enrichment
---

# Waterfall-Enrich Contacts with External Providers

Fill missing emails, phone numbers, and job titles on HubSpot contacts using an external enrichment provider, then write results back with a full audit trail. The provider layer is pluggable: **FullEnrich** (a waterfall aggregator that queries 20+ upstream sources until one hits) is the default, with Apollo, Hunter, and Dropcontact adapters included and a template for whatever provider your team already pays for.

## Why This Matters

The internal enrichment skills (`/enrich-company-name`, `/enrich-industry`, `/backfill-geo-data`) only move data the portal already has. When a contact's email, direct dial, or title simply isn't anywhere in HubSpot, external enrichment is the only fix — and it costs real money per lookup, which is why this skill is built around cost caps, previews, and typed confirmations.

## Provider Landscape

| Provider | Adapter | Strength | Model |
|----------|---------|----------|-------|
| **FullEnrich** (default) | `providers/fullenrich.py` | Waterfall across 20+ sources — best hit rates for email + mobile | Credits per lookup, async bulk API |
| Apollo | `providers/apollo.py` | Large B2B database, titles + firmographics | Credits; personal-data reveals plan-gated |
| Hunter | `providers/hunter.py` | Email finding by name+domain, confidence scores | Requests per plan; email only |
| Dropcontact | `providers/dropcontact.py` | GDPR-first, algorithmic (no stored database) | Credits, async |
| Your provider | copy `providers/_template.py` | Whatever you already use | — |
| HubSpot Breeze Intelligence | (native, no adapter) | In-platform enrichment + form shortening | Credit add-on; programmatic API access is enterprise-gated — which is exactly why this skill defaults to provider-agnostic adapters |

Switch providers with one env var: `ENRICHMENT_PROVIDER=apollo`.

## Prerequisites

- A HubSpot private app access token (`HUBSPOT_ACCESS_TOKEN` in `.env`) with contact read/write scopes
- Python 3.10+ with [`uv`](https://github.com/astral-sh/uv)
- An account + API key with your chosen provider (e.g. `FULLENRICH_API_KEY` from FullEnrich dashboard > Settings > API)
- **A compliance check**: enrichment sends contact names and company data to a third party and imports personal data (emails, phones). Confirm this fits your data processing agreements and the applicable privacy rules (GDPR/CCPA) *before* running.

## Scripts

| Stage | Script | Run with |
|-------|--------|----------|
| Before | [`scripts/before.py`](./scripts/before.py) | `uv run skills/waterfall-enrich-contacts/scripts/before.py` |
| Execute | [`scripts/execute.py`](./scripts/execute.py) | `uv run skills/waterfall-enrich-contacts/scripts/execute.py` |
| After | [`scripts/after.py`](./scripts/after.py) | `uv run skills/waterfall-enrich-contacts/scripts/after.py` |

Provider adapters live in [`scripts/providers/`](./scripts/providers/) — one module per provider implementing `enrich(contacts) -> results` (see `_template.py` for the contract).

## Configuration

Everything is set in `.env`:

```
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx
ENRICHMENT_PROVIDER=fullenrich          # fullenrich | apollo | hunter | dropcontact | yours
FULLENRICH_API_KEY=...                  # the chosen provider's key
ENRICHMENT_TARGET_FIELD=phone           # phone | email | jobtitle
ENRICHMENT_MAX_CONTACTS=100             # hard cap per run — credits cost money
ENRICHMENT_OVERWRITE=false              # never overwrite existing values (default)
ENRICHMENT_CREDITS_PER_CONTACT=1        # for before.py's cost preview
```

## Execution Pattern

### Stage 1: Plan

1. Choose the provider and the target field (a phone backfill and an email backfill are separate runs).
2. Confirm the compliance check above with whoever owns data privacy.
3. Confirm budget: `MAX_CONTACTS × credits-per-lookup` is the per-run ceiling. Start with a small run (25-50) and inspect quality before scaling.

### Stage 2: Before

```bash
uv run skills/waterfall-enrich-contacts/scripts/before.py
```

Counts candidates (contacts with first name + last name + company but missing the target field) and prints a cost ceiling. Read-only.

### Stage 3: Execute

```bash
uv run skills/waterfall-enrich-contacts/scripts/execute.py
```

The script:
1. Selects up to `MAX_CONTACTS` candidates via the Search API
2. Asks for typed confirmation (`ENRICH`) **before spending credits**
3. Calls the provider adapter (async providers poll until done)
4. Computes writes — existing non-empty HubSpot values are never overwritten unless `ENRICHMENT_OVERWRITE=true`; skipped values are still recorded in the audit CSV
5. Asks for a second typed confirmation (`WRITE`) before touching HubSpot
6. Batch-updates contacts and writes the audit CSV (old value, new value, action, source per field)

### Stage 4: After

```bash
uv run skills/waterfall-enrich-contacts/scripts/after.py
```

Compares candidate counts against the baseline, then **spot-check 10-20 enriched contacts by hand** — provider quality varies by segment, and the audit CSV tells you exactly what was written where.

## Safety Mechanisms

| Mechanism | Detail |
|-----------|--------|
| **Per-run cap** | `MAX_CONTACTS` (default 100) bounds credit spend per run. Deliberately low — raise it only after verifying quality. |
| **No-overwrite default** | Existing non-empty values are never replaced unless `ENRICHMENT_OVERWRITE=true`. Enrichment fills gaps; it does not correct data. |
| **Double confirmation** | Typed `ENRICH` before credits are spent; typed `WRITE` before HubSpot is touched. Aborting between the two costs credits but changes nothing. |
| **CSV audit trail** | Every field written (and every skip) recorded with old value, new value, and provider source. |
| **Rollback data** | The audit CSV's `old` column is the rollback: batch-update those values back to undo a run. |

## Rollback

- The execute audit CSV records the previous value of every field it wrote. To undo, batch-update those contact/field pairs back to the `old` values (empty string clears a field).
- Values are also individually recoverable from each contact's property history.

## Technical Gotchas

1. **Verify adapter payloads against current provider docs.** Provider APIs move fast; each adapter's docstring links the docs and flags what to check. The adapters fail loudly (clear `SystemExit` messages) on auth or credit errors before touching HubSpot.
2. **Waterfall providers are asynchronous.** FullEnrich and Dropcontact return results in seconds-to-minutes; the adapters poll. Don't kill the script mid-poll — credits are consumed at submission.
3. **Enriched emails are unverified senders' risk.** A found email is not consent to market. New emails enter as non-marketing data points; your normal opt-in and deliverability rules apply before any sends.
4. **Match rates of 40-70% are normal.** Providers can't find everyone. The audit CSV separates "provider found nothing" (absent) from "found but skipped" (existing value).
5. **Domain quality drives hit rates.** Candidates whose email domain or company website is missing enrich poorly. Run `/enrich-company-name` first — better identity inputs, better waterfall results.
6. **Internal-data-first.** If the value exists anywhere in the portal (associated company, `ip_country`, form submissions), the free internal skills should fill it — save credits for data HubSpot genuinely doesn't have.
