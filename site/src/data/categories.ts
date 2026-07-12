/**
 * The six skill categories — the site-side mirror of the category table in
 * CONTRIBUTING.md. `metadata.category` in every SKILL.md must be one of
 * these slugs (enforced by the content schema, which fails the build on
 * anything else).
 */

export interface Category {
  slug: string;
  title: string;
  description: string;
  intro: string;
  icon: string;
}

export const CATEGORIES = [
  {
    slug: 'audit-planning',
    title: 'Audit & Planning',
    description: 'Portal assessment, connectivity, and implementation planning.',
    intro:
      'Start here: grade the state of your portal, plan the cleanup in dependency order, wire up connections, and verify the toolkit against a sandbox before trusting it with production.',
    icon: 'tabler:report-search',
  },
  {
    slug: 'database-hygiene',
    title: 'Database Hygiene',
    description: 'Removing bad data, suppressing contacts, deduplication.',
    intro:
      'The highest-impact fixes: delete unusable records, suppress contacts that hurt deliverability or inflate billing, merge duplicates, and reassign orphaned ownership.',
    icon: 'tabler:database',
  },
  {
    slug: 'data-enrichment',
    title: 'Data Enrichment',
    description: 'Filling gaps in contact and company data.',
    intro:
      'Fill the gaps that block segmentation and scoring — from your own associated records first, and from external waterfall providers when internal data runs out.',
    icon: 'tabler:sparkles',
  },
  {
    slug: 'segmentation-scoring',
    title: 'Segmentation & Scoring',
    description: 'ICP tiers, lead scoring, smart lists.',
    intro:
      'Turn a clean database into a usable one: classify accounts against your ICP, score fit and engagement, and build the lists your campaigns and reports run on.',
    icon: 'tabler:chart-bar',
  },
  {
    slug: 'automation-workflows',
    title: 'Automation Workflows',
    description: 'HubSpot workflows for ongoing hygiene.',
    intro:
      'Prevention instead of cleanup: workflows — created via the v4 Automation API, always disabled for review — that keep new data clean, progress lifecycles, and suppress disengagement automatically.',
    icon: 'tabler:settings-automation',
  },
  {
    slug: 'ongoing-maintenance',
    title: 'Ongoing Maintenance',
    description: 'Recurring cleanup and health checks.',
    intro:
      'Keep it clean: weekly and quarterly routines plus targeted cleanups for lists, forms, workflows, dashboards, deals, properties, and owners.',
    icon: 'tabler:calendar-repeat',
  },
] as const satisfies readonly Category[];

export type CategorySlug = (typeof CATEGORIES)[number]['slug'];

export const CATEGORY_SLUGS = CATEGORIES.map((c) => c.slug) as [CategorySlug, ...CategorySlug[]];

export const getCategory = (slug: CategorySlug): Category => {
  const category = CATEGORIES.find((c) => c.slug === slug);
  if (!category) throw new Error(`Unknown category slug: ${slug}`);
  return category;
};
