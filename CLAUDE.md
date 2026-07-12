# HubSpot Admin Skills

This is a Claude Code skills marketplace plugin for HubSpot CRM administration.

## Conventions

- Each skill lives in `skills/<skill-name>/SKILL.md`; skills with scripted stages ship `scripts/before.py`, `scripts/execute.py`, `scripts/after.py`
- Skills follow the Agent Skills Specification: context, prerequisites, step-by-step instructions, verification checks, and rollback guidance
- Skills that change portal state follow the **Plan → Before → Execute → After** pattern with a required **Rollback** section, an abort threshold, a CSV audit trail, and explicit user confirmation before mutating anything
- The repo is organized by CRM lifecycle phase: audit, hygiene, enrichment, segmentation, automation, and ongoing maintenance
- All content is company-agnostic — no customer data, credentials, or proprietary references
- Scripts are plain Python using `requests` against HubSpot REST endpoints directly (no SDK wrapper), with PEP 723 inline metadata, run via `uv run skills/<skill>/scripts/<stage>.py`
- Authentication: `HUBSPOT_ACCESS_TOKEN` (private app token) loaded from `.env` via `python-dotenv`
- CSV audit logs go to `data/audit-logs/` (gitignored — may contain PII, never commit)
- API targets: `/crm/v3/`, `/automation/v4/`, `/marketing/v3/` — supported until March 30, 2027; HubSpot's date-based versions (`2026-03`) are the future migration target
- See `CONTRIBUTING.md` for the full skill template, frontmatter spec, and safety-mechanism requirements
