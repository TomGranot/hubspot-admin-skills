# Programmatic SEO Site Plan — `hubspot.granot.io`

A plan for an agent-first, auto-deployed programmatic SEO site generated from this repo. The site's single source of truth is the `skills/` directory: every skill merged to `main` automatically becomes a set of pages, and the community-contribution flywheel (audit skill → new skill → PR) becomes a content flywheel.

## Goals

1. **Rank for HubSpot admin long-tail queries** — "hubspot contacts without lifecycle stage", "merge duplicate companies hubspot api", "suppress hard bounced contacts hubspot" — and funnel readers (human or agent) toward installing the plugin.
2. **Be genuinely consumable by agents** — every page has a raw-markdown twin, an `llms.txt` index, and a JSON manifest, so a coding agent can discover, evaluate, and install a skill without scraping HTML.
3. **Zero-touch operation** — merging a skill PR is the only publishing action. No CMS, no manual sync, no separate content repo.

## Architecture

### Content model

The `SKILL.md` files are the content. The build reads `skills/*/SKILL.md`, parses the YAML frontmatter (`name`, `description`, `license`, `metadata.author/version/category`) and the markdown body, and derives everything else:

| Derived field | Source |
|---|---|
| Page title / H1 | First `#` heading in body |
| Meta description | `description` frontmatter |
| Category hub membership | `metadata.category` |
| "Scripted" badge | Presence of `scripts/` dir (and which of `before.py` / `execute.py` / `after.py` exist) |
| Problem statement | "Why This Matters" section |
| Related skills | Same category + explicit cross-references found in the body |

No frontmatter changes are required to launch. **Optional later**: add `keywords`, `related`, and `hubspot_plan` fields to frontmatter for richer targeting — the build must treat all of these as optional so existing and community skills never break.

### Tech stack

- **Astro** static site generator, living in a `site/` directory of this repo (monorepo — keeps the auto-rebuild trivial and lets skill PRs and site PRs share CI).
  - Content collections with a loader that reads `../skills/*/SKILL.md` — no copying, no sync step.
  - Zero client-side JS by default; pages are plain HTML. Fast, crawlable, cheap.
- **GitHub Pages** for hosting, deployed by GitHub Actions. Free, no new accounts, first-class custom-domain support for `hubspot.granot.io`. (Cloudflare Pages is the fallback if we later need redirects/headers/edge logic; the Astro build output is host-agnostic so switching is cheap.)
- **No client analytics at launch.** Add Plausible/Cloudflare analytics later if wanted; keep pages script-free for agent friendliness.

### Repo layout

```
hubspot-admin-skills/
├── skills/                  # unchanged — single source of truth
├── site/
│   ├── astro.config.mjs
│   ├── package.json
│   ├── src/
│   │   ├── content.config.ts    # loader over ../skills/*/SKILL.md
│   │   ├── data/
│   │   │   ├── categories.ts    # 6 category slugs → titles, intros, ordering
│   │   │   └── problems.ts      # problem-page definitions (see below)
│   │   ├── layouts/
│   │   └── pages/
│   └── public/              # robots.txt, favicon, hero
└── .github/workflows/
    └── deploy-site.yml
```

## Page inventory (URL map)

All URLs relative to `https://hubspot.granot.io`.

### Human + agent pages (HTML, with `.md` twins)

| Route | Count | Purpose |
|---|---|---|
| `/` | 1 | Landing: what the plugin does, install commands, audit→plan→execute story, category grid |
| `/skills/` | 1 | Full index of all skills, grouped by category |
| `/skills/<slug>/` | 32+ | One page per skill, rendered from `SKILL.md` — the core programmatic surface |
| `/categories/<slug>/` | 6 | Category hubs (audit-planning, database-hygiene, data-enrichment, segmentation-scoring, automation-workflows, ongoing-maintenance) with intro copy + skill list |
| `/problems/<slug>/` | ~30 at launch | Problem-first pages (see "Programmatic SEO strategy") |
| `/install/` | 1 | Install instructions for humans **and** a copy-pasteable prompt block for agents ("paste this into Claude Code") |
| `/contributing/` | 1 | The community flywheel: how the audit skill creates and PRs new skills |

### Agent-only surfaces

| Route | Purpose |
|---|---|
| `/llms.txt` | Per the llms.txt spec: site summary + curated links to the `.md` versions of every page |
| `/llms-full.txt` | Concatenated full markdown of all skills, for single-fetch ingestion |
| `/skills/<slug>.md` | Raw SKILL.md content (verbatim, frontmatter included) |
| `/skills/<slug>/scripts/<name>.py` | Raw script files for scripted skills |
| `/api/skills.json` | Machine-readable manifest: slug, name, description, category, version, scripted flags, source URL, install command |
| `/sitemap.xml`, `/robots.txt` | robots.txt explicitly **allows** GPTBot, ClaudeBot, PerplexityBot, etc. |

Every HTML page includes `<link rel="alternate" type="text/markdown" href="….md">` and a visible "View as Markdown / for agents" link, so both crawlers and agents landing on HTML can find the raw form.

## Programmatic SEO strategy

The honest constraint: 32 skills ≈ 32 core pages, which is small for classic pSEO. The multiplier comes from three places:

1. **Problem pages (`/problems/`)** — each skill answers 1–3 distinct search intents phrased as problems, not solutions. `fix-lifecycle-stages` → "HubSpot contacts missing lifecycle stage", "HubSpot lifecycle stage won't change backwards" (that forward-only gotcha is genuinely searched and the SKILL.md already documents it well). These are defined in `site/src/data/problems.ts` as `{slug, title, intent, skill, excerpt-sections}` and render the relevant SKILL.md sections plus a "fix it with one command" CTA. Start with ~1 per skill, expand based on Search Console data.
2. **The contribution flywheel** — every community skill merged to `main` ships pages automatically. The README already promises the audit skill will generate and PR new skills; the site makes each of those a ranking asset.
3. **Deep content quality over page count** — SKILL.md files contain real API code, gotchas, and rollback procedures. That's exactly what thin pSEO competitors lack, and it wins both classic ranking and LLM citation (AI Overviews / assistant answers quoting the site).

### On-page SEO mechanics

- **JSON-LD** on every skill page: `TechArticle` + `HowTo` (the Plan→Before→Execute→After stages map cleanly to HowTo steps) + `SoftwareSourceCode` for scripted skills. `FAQPage` on problem pages where sections naturally answer questions.
- Titles patterned `"<Problem/Skill> — HubSpot Admin Skills"`, descriptions from frontmatter.
- Heavy internal linking: skill ↔ category ↔ problem ↔ related skills (same category), plus every page linking to `/install/`.
- Canonicals on problem pages pointing to themselves (they're distinct intents, not duplicates), skill `.md` twins marked `noindex` via `X-Robots-Tag`-equivalent meta on the HTML side only (raw `.md` files served as text don't compete).
- OG images: one static branded template at launch; per-page generated OG images (satori/astro-og) in phase 2.

## CI/CD

`.github/workflows/deploy-site.yml`:

- **Triggers**: push to `main` touching `skills/**` or `site/**`; manual `workflow_dispatch`.
- **Steps**: checkout → setup node → `npm ci && npm run build` in `site/` → validate step (fails the build if any SKILL.md has missing/invalid frontmatter — doubles as a lint gate for skill PRs) → deploy to GitHub Pages via `actions/deploy-pages`.
- **PR previews**: on PRs touching `skills/**`, run build-only (no deploy) as a required check, so malformed community skills can't break the site.
- Build is deterministic from repo content — no external data sources, no tokens.

## Domain

1. Launch on `tomgranot.github.io/hubspot-admin-skills` (or straight to the custom domain if DNS is ready).
2. Connect `hubspot.granot.io`: CNAME record → `tomgranot.github.io`, set custom domain in repo Pages settings, enforce HTTPS. `site/public/CNAME` checked in so deploys don't drop it.
3. Set `site:` in `astro.config.mjs` to the final domain so sitemap/canonical/OG URLs are absolute and correct.
4. Register the property in Google Search Console + Bing Webmaster Tools, submit sitemap.

## Phases

### Phase 1 — Foundation (ship first)
- Scaffold Astro in `site/`, content loader over `skills/`, base layout + design.
- Homepage, `/skills/` index, 32 skill pages, 6 category hubs, `/install/`.
- `.md` twins, `/llms.txt`, `/llms-full.txt`, `/api/skills.json`, sitemap, robots.
- Deploy workflow + GitHub Pages live.

### Phase 2 — Programmatic depth
- `/problems/` pages (~30), JSON-LD everywhere, related-skills cross-linking.
- Frontmatter linter as a required PR check; per-page OG images.
- Connect `hubspot.granot.io`, Search Console, submit sitemap.

### Phase 3 — Growth (data-driven)
- Expand problem pages from Search Console query data.
- Optional: HubSpot admin glossary (`/glossary/<term>/`) for another long-tail surface.
- Optional: lightweight analytics (Plausible).
- Optional: an MCP server / `.well-known` discovery endpoint exposing the skills manifest, once agent-side conventions settle.

## Open questions

1. **Hosting**: GitHub Pages assumed. Fine, or prefer Cloudflare Pages/Vercel from day one?
2. **Branding**: reuse the hero/visual identity from `assets/hero.png` and consume.granot.io, or a fresh look for the site?
3. **Problem-page copy**: generated excerpts from SKILL.md are the default; any appetite for hand-written intros on the top ~10 pages for quality?
