# HubSpot Admin Skills

This is a Claude Code skills marketplace plugin for HubSpot CRM administration.

## Conventions

- Each skill lives in `skills/<skill-name>/SKILL.md`
- Skills follow the Agent Skills Specification: context, prerequisites, step-by-step instructions, verification checks, and rollback guidance
- The repo is organized by CRM lifecycle phase: audit, hygiene, enrichment, segmentation, automation, and ongoing maintenance
- All content is company-agnostic — no customer data, credentials, or proprietary references
- Skills that support scripted execution use Python with the `hubspot-api-client` package and assume `uv` for dependency management
