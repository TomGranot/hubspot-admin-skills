import { getCollection, type CollectionEntry } from 'astro:content';

import { getSkill, type Skill } from '~/lib/skills';

export type GuideEntry = CollectionEntry<'guides'>;

export interface Guide {
  slug: string;
  title: string;
  description: string;
  heading: string;
  updated: Date;
  skills: Skill[];
  entry: GuideEntry;
}

export const guidePath = (slug: string) => `/guides/${slug}`;

let cache: Promise<Guide[]> | undefined;

/** All guides, in display order. A guide that names a missing skill fails the build. */
export const getGuides = (): Promise<Guide[]> =>
  (cache ??= (async () => {
    const entries = await getCollection('guides');
    const guides = await Promise.all(
      entries.map(async (entry) => ({
        slug: entry.id,
        title: entry.data.title,
        description: entry.data.description,
        heading: entry.data.heading,
        updated: entry.data.updated,
        skills: await Promise.all(entry.data.skills.map((slug) => getSkill(slug))),
        entry,
      }))
    );
    const order = new Map(entries.map((e) => [e.id, e.data.order]));
    return guides.sort((a, b) => (order.get(a.slug) ?? 0) - (order.get(b.slug) ?? 0));
  })());
