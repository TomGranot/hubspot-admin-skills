# HubSpot Admin Skills

This is a Claude Code skills marketplace plugin for HubSpot CRM administration.

## Conventions

- Each skill lives in `skills/<skill-name>/SKILL.md`; skills with scripted stages ship `scripts/before.py`, `scripts/execute.py`, `scripts/after.py`
- Skills follow the Agent Skills Specification: context, prerequisites, step-by-step instructions, verification checks, and rollback guidance
- Skills that change portal state follow the **Plan → Before → Execute → After** pattern with a required **Rollback** section, an abort threshold, a CSV audit trail, and explicit user confirmation before mutating anything
- The repo is organized by CRM lifecycle phase: audit, hygiene, enrichment, segmentation, automation, and ongoing maintenance
- All content is company-agnostic — no customer data, credentials, or proprietary references
- Scripts are plain Python using `requests` against HubSpot REST endpoints directly (no SDK wrapper), with PEP 723 inline metadata, run via `uv run skills/<skill>/scripts/<stage>.py`
- Authentication: `HUBSPOT_ACCESS_TOKEN` loaded from `.env` via `python-dotenv`. The token is a service key; legacy private app tokens still work but can no longer be created (since October 26, 2026), so never tell a user to create a private app
- CSV audit logs go to `data/audit-logs/` (gitignored — may contain PII, never commit)
- API targets: existing scripts use `/crm/v3/`, `/automation/v4/`, `/marketing/v3/`. v4 support ends March 30, 2027; v1-v3 are unsupported since September 2026 with enforcement in September 2027. New scripts target the current date-based version (`2026-09`); existing scripts migrate one skill at a time, each verified with `/sandbox-self-test`
- Rate limits: 100 requests per 10 seconds per app on Free/Starter, 190 on Professional/Enterprise; the Search API is capped separately at 5 requests per second
- See `CONTRIBUTING.md` for the full skill template, frontmatter spec, and safety-mechanism requirements
