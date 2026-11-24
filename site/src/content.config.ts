import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { glob } from 'astro/loaders';

import { CATEGORY_SLUGS } from './data/categories';

// The skills/ directory at the repo root is the single source of truth.
// This schema doubles as the lint gate for community skill PRs: a SKILL.md
// with missing or malformed frontmatter fails the site build (and therefore
// the Netlify deploy preview).
const skillsCollection = defineCollection({
  loader: glob({ pattern: '*/SKILL.md', base: '../skills' }),
  schema: z.object({
    name: z.string().min(1),
    description: z.string().min(1),
    license: z.string().min(1),
    metadata: z.object({
      author: z.string().min(1),
      version: z.string().min(1),
      category: z.enum(CATEGORY_SLUGS),
    }),
  }),
});

// Long-form guides that answer a search query in full (manual steps first,
// the scripted skill second). Lives in the site, not in skills/, because a
// guide is not a skill and must not be installed as one.
const guidesCollection = defineCollection({
  loader: glob({ pattern: '*.md', base: './src/content/guides' }),
  schema: z.object({
    // <title> tag, rendered without the site suffix: keep it to 60 characters.
    title: z.string().min(1).max(60),
    description: z.string().min(120).max(165),
    heading: z.string().min(1),
    updated: z.coerce.date(),
    // Skill slugs shown as cards at the end of the guide. Validated at build time.
    skills: z.array(z.string()).min(1),
    order: z.number().int(),
  }),
});

export const collections = {
  skills: skillsCollection,
  guides: guidesCollection,
};
