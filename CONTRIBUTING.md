# Contributing to HubSpot Admin Skills

Every HubSpot portal is different, and the skill set grows by admins contributing the fixes they've battle-tested on their own portals. This guide defines the house style so that every skill feels like part of the same toolkit.

## The Fast Path

The `hubspot-audit` skill detects issues that no existing skill covers and offers to create new ones on the spot. If you accept, Claude Code creates the skill, pushes it to your fork, and opens a PR — you don't need to know git or write markdown. Everything below is for manual contributions (and for Claude, when generating skills automatically).

## Manual Contributing

1. **Fork**: `gh repo fork TomGranot/hubspot-admin-skills --clone`
2. **Branch**: `git checkout -b skill/your-skill-name`
3. **Create**: Add `skills/<your-skill>/SKILL.md` following the spec below
4. **Test**: Run the skill against a HubSpot sandbox portal
5. **PR**: `gh pr create --repo TomGranot/hubspot-admin-skills`

## Skill Anatomy

```
skills/<skill-name>/
├── SKILL.md              # Required
└── scripts/              # Optional — only for skills with scripted stages
    ├── before.py
    ├── execute.py
    └── after.py
```

### Frontmatter

Every SKILL.md starts with this exact frontmatter shape. Use a single-line, double-quoted `description`:

```yaml
---
name: skill-slug
description: "One or two sentences. What the skill does and when to use it."
license: MIT
metadata:
  author: your-github-handle
  version: "1.0"
  category: database-hygiene
---
```

### Categories

| Category | Slug | Description |
|----------|------|-------------|
| Audit & Planning | `audit-planning` | Portal assessment, connectivity, and implementation planning |
| Database Hygiene | `database-hygiene` | Removing bad data, suppressing contacts, deduplication |
| Data Enrichment | `data-enrichment` | Filling gaps in contact/company data |
| Segmentation & Scoring | `segmentation-scoring` | ICP tiers, lead scoring, smart lists |
| Automation Workflows | `automation-workflows` | HubSpot workflows for ongoing hygiene |
| Ongoing Maintenance | `ongoing-maintenance` | Recurring cleanup and health checks |

### The 4-Stage Execution Pattern

Every skill that changes portal state follows **Plan → Before → Execute → After**, plus a **Rollback** section:

| Stage | What happens |
|-------|-------------|
| **Plan** | Explain the approach, confirm root causes, thresholds, and configuration with the user |
| **Before** | Audit current state, export a CSV baseline, show the user exactly what will change |
| **Execute** | Make the changes (scripts or step-by-step UI instructions) |
| **After** | Verify the fix, compare before/after, confirm success |

**Rollback** is a required section (not a stage): state how to undo the change, or state plainly that it cannot be undone and what to export beforehand.

Read-only skills (audits, reviews) may collapse this to Before/Execute/After where Plan adds nothing.

### Safety Mechanisms

Skills that mutate data must include a `## Safety Mechanisms` table covering, at minimum:

| Mechanism | Requirement |
|-----------|-------------|
| **Abort threshold** | Hard-coded count above which the script exits without changing anything. Scale it to destructiveness: deletions default to low hundreds (e.g. 500); reversible bulk property updates may go much higher (e.g. 50,000). State the rationale. |
| **CSV audit trail** | Export every affected record (ID + key properties) *before* mutating anything. |
| **Confirmation prompt** | Present the Before count to the user and wait for explicit confirmation. Destructive scripts additionally require typed confirmation (e.g. `input("Type 'DELETE' to confirm: ")`). |
| **Recovery window** | State what HubSpot can restore (e.g. deleted contacts: 90 days via Settings > Data Management > Deleted Objects) and what it cannot. |

Workflows created via the API must always be created **disabled** (`isEnabled: false`) so the user reviews them in the UI before turning them on.

## Python Script House Style

Skills that support scripted execution ship plain-Python scripts using **`requests` against HubSpot's REST endpoints directly** — not an SDK wrapper. This keeps scripts dependency-light, transparent about exactly which endpoint and payload they use, and immune to SDK release lag.

Every script:

1. **Carries PEP 723 inline metadata** and is executed with `uv run` — no project setup, no `pip install`:

   ```python
   # /// script
   # requires-python = ">=3.10"
   # dependencies = [
   #   "requests>=2.31",
   #   "python-dotenv>=1.0",
   # ]
   # ///
   ```

   ```bash
   uv run skills/<skill-name>/scripts/before.py
   ```

2. **Authenticates via `HUBSPOT_ACCESS_TOKEN`** from a `.env` file at the repo root (fall back to the script's skill directory):

   ```python
   from dotenv import load_dotenv
   load_dotenv()  # .env in the working directory
   load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

   TOKEN = os.environ["HUBSPOT_ACCESS_TOKEN"]
   BASE = "https://api.hubapi.com"
   HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
   ```

3. **Paginates with the `after` cursor** (`limit: 100`), sleeping ~0.15–0.2s between pages; batch mutations in groups of 100 with ~0.5s between batches; retry on HTTP 429 with backoff.

4. **Writes CSV audit logs to `data/audit-logs/<skill-name>-<stage>.csv`** relative to the working directory (`os.makedirs("data/audit-logs", exist_ok=True)`). The `data/` directory is gitignored — audit logs may contain PII and must never be committed.

5. **Never hard-codes** portal IDs, owner IDs, property values, or anything company-specific. Configuration goes in a clearly marked `# --- Configuration ---` block at the top.

SKILL.md files should reference their scripts in a `## Scripts` table (stage → path → purpose) rather than duplicating full listings inline. Short inline snippets are fine where they teach an API concept (a filter payload, a gotcha).

## API Version Policy

- Scripts target the REST versions that are stable and supported today: `/crm/v3/`, `/automation/v4/`, `/marketing/v3/`.
- HubSpot moved to date-based API versioning (`/YYYY-MM/`, currently `2026-03`) in March 2026; legacy v1–v4 APIs are supported until **March 30, 2027**. This repo will migrate to date-based paths in a future major version — new skills should not add dependencies on v1/v2 legacy endpoints.
- When a skill works around an API limitation ("read-only via API", "UI only"), cite it in a **Key Constraint** or **Technical Gotchas** section with enough context that future contributors can re-verify it.

## Content Rules

- **Company-agnostic, always.** No customer data, API keys, portal IDs, or proprietary references.
- Authoritative practitioner voice: explain *why* before *how*. No emojis.
- External products (enrichment providers, AI assistants) are options, never requirements — the default path must work with a HubSpot private app token alone, except where the skill's entire purpose is the external integration.
