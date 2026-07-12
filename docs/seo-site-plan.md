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

- **Astro 6** static site generator, living in a `site/` directory of this repo (monorepo — keeps the auto-rebuild trivial and lets skill PRs and site PRs share CI).
  - Based on the **AstroWind** template (Tailwind CSS v4) — the most popular Astro theme, with production-grade SEO plumbing (astro-seo metadata, sitemap, image optimization, dark mode) and reusable marketing widgets. Demo content stripped; layout, widgets, and SEO components kept.
  - Content collection with a `glob()` loader reading `../skills/*/SKILL.md` — no copying, no sync step. The zod schema doubles as a frontmatter lint gate: a malformed community skill fails the build (and therefore the deploy preview).
  - Zero client-side JS beyond the theme's small UI scripts; pages are plain HTML. Fast, crawlable, cheap.
- **Netlify** for hosting, auto-deployed from GitHub. `netlify.toml` at the repo root sets `base = "site"`, and an `ignore` rule skips builds for commits that touch neither `site/` nor `skills/`. Deploy previews on PRs act as the CI gate for community skills.
- **No client analytics at launch.** Add Plausible/Netlify analytics later if wanted; keep pages script-free for agent friendliness.

### Repo layout

```
hubspot-admin-skills/
├── skills/                  # unchanged — single source of truth
├── netlify.toml             # base=site, ignore rule, Node version
├── site/
│   ├── astro.config.ts
│   ├── package.json
│   ├── scripts/
│   │   └── postbuild-headers.mjs  # generates dist/_headers (content types, canonical Links)
│   ├── src/
│   │   ├── content.config.ts    # glob loader over ../skills/*/SKILL.md + frontmatter schema
│   │   ├── config.yaml          # site name/URL, default metadata (AstroWind)
│   │   ├── data/
│   │   │   ├── categories.ts    # 6 category slugs → titles, intros, ordering
│   │   │   └── problems.ts      # 33 problem-page definitions (see below)
│   │   ├── lib/
│   │   │   ├── skills.ts        # skill model: slugs, scripts detection, excerpts, URLs
│   │   │   └── structuredData.ts # JSON-LD builders
│   │   ├── layouts/ | components/ | pages/
│   │   └── ...
│   └── public/              # robots.txt, favicons
└── docs/seo-site-plan.md    # this plan
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

## CI/CD (Netlify)

No GitHub Actions needed — Netlify handles the whole pipeline:

- **Production deploys**: every push to `main` touching `site/**`, `skills/**`, or `netlify.toml` triggers a build (`npm run build` with `base = "site"`, publishing `site/dist`). Other commits are skipped via the `ignore` rule in `netlify.toml`.
- **Deploy previews**: every PR gets a preview URL automatically. Because the content-collection schema validates SKILL.md frontmatter at build time, a malformed community skill fails its deploy preview — that's the lint gate.
- **Headers**: `site/scripts/postbuild-headers.mjs` generates `dist/_headers` after each build — long-cache for hashed assets, CORS for everything, `text/markdown` content-type plus a canonical `Link` header for every `.md` twin (Netlify's `_headers` syntax can't pattern-match `*.md` mid-path, so exact paths are generated from `skills/`).
- Build is deterministic from repo content — no external data sources, no tokens.

### One-time Netlify dashboard setup (manual)

1. Netlify → **Add new site → Import an existing project** → pick `TomGranot/hubspot-admin-skills`. Build settings are read from `netlify.toml` automatically; just confirm and deploy.
2. Verify the first deploy on the generated `*.netlify.app` URL.

## Domain

1. Netlify site settings → **Domain management → Add custom domain** → `hubspot.granot.io`.
2. In DNS for `granot.io`: `CNAME hubspot → <site-name>.netlify.app`. Netlify provisions Let's Encrypt HTTPS automatically.
3. `site:` in `src/config.yaml` is already `https://hubspot.granot.io`, so sitemap/canonical/OG URLs are correct from the first deploy.
4. Register the property in Google Search Console + Bing Webmaster Tools, submit `sitemap-index.xml`.

## Phases

### Phase 1 — Foundation ✅ (built)
- AstroWind-based site in `site/`, content loader over `skills/`.
- Homepage, `/skills/` index, 32 skill pages, 6 category hubs, `/install/`, `/contributing/`.
- `.md` twins, raw script endpoints, `/llms.txt`, `/llms-full.txt`, `/api/skills.json`, sitemap, agent-welcoming robots.txt.
- `netlify.toml` + generated `_headers`; deploy is connect-the-repo away.

### Phase 2 — Programmatic depth ✅ (built)
- 33 `/problems/` intent pages with FAQ content, cross-linked from skill pages.
- JSON-LD everywhere: TechArticle + HowTo (+ SoftwareSourceCode for scripted skills) on skill pages, FAQPage on problem pages, BreadcrumbList throughout, WebSite/Organization on the homepage.
- Frontmatter validation as part of the build (fails deploy previews on malformed skills).
- Per-page generated OG images (SVG → PNG via sharp at build time) for all skill and problem pages.
- Remaining (manual): connect `hubspot.granot.io`, register Search Console + Bing Webmaster Tools, submit sitemap.

### Phase 3 — Growth (data-driven, not started)
- Expand problem pages from Search Console query data.
- A recurring (daily/weekly) agent routine that reviews Search Console/Bing data and site state, then proposes/creates new problem pages and improvements.
- Optional: HubSpot admin glossary (`/glossary/<term>/`) for another long-tail surface.
- Optional: lightweight analytics (Plausible/Netlify).
- Optional: an MCP server / `.well-known` discovery endpoint exposing the skills manifest, once agent-side conventions settle.

## Resolved decisions

1. **Hosting**: Netlify (repo-root `netlify.toml`, base `site/`, deploy previews as the PR gate).
2. **Theme**: AstroWind template (Astro 6 + Tailwind v4), demo content stripped.
3. **Branding**: reuses `assets/hero.png` and the repo's visual identity.
4. **Problem-page copy**: hand-written intros + FAQs for all 33 launch pages (in `site/src/data/problems.ts`), with excerpts pulled from each skill's "Why This Matters" section.
