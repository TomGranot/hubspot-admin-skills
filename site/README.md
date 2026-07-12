# hubspot.granot.io — programmatic SEO site

The public site for [HubSpot Admin Skills](https://github.com/TomGranot/hubspot-admin-skills), generated entirely from the `skills/*/SKILL.md` files at the repo root. Merging a skill PR to `main` is the only publishing action — the site rebuilds and gains pages automatically.

Built with [Astro 6](https://astro.build) on the [AstroWind](https://github.com/onwidget/astrowind) template (Tailwind CSS v4), deployed to Netlify (see `../netlify.toml` and `../docs/seo-site-plan.md` for the full plan).

## Page inventory

| Route | Source |
| --- | --- |
| `/`, `/install`, `/contributing` | `src/pages/*.astro` |
| `/skills` + `/skills/<slug>` | generated from `../skills/*/SKILL.md` |
| `/categories/<slug>` | `src/data/categories.ts` |
| `/problems` + `/problems/<slug>` | `src/data/problems.ts` (search-intent pages) |
| `/skills/<slug>.md` | verbatim SKILL.md (raw-markdown twin for agents) |
| `/skills/<slug>/scripts/<stage>.py` | raw Python scripts |
| `/llms.txt`, `/llms-full.txt`, `/api/skills.json` | agent surfaces |
| `/og/**.png` | build-time generated Open Graph images |

## Development

```bash
npm install
npm run dev      # dev server
npm run build    # astro build + generates dist/_headers
npm run preview  # serve dist/
```

The content-collection schema in `src/content.config.ts` validates SKILL.md frontmatter — a malformed skill fails the build, which is what makes Netlify deploy previews act as the lint gate for community skill PRs.
