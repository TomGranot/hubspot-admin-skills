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

export const collections = {
  skills: skillsCollection,
};
