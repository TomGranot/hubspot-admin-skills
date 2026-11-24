/**
 * Search-facing title and meta description overrides for skill pages.
 *
 * Do not "fix" these by editing a SKILL.md instead: its frontmatter
 * `description` is what Claude Code reads to decide when to run the skill,
 * and it also feeds skills.json and llms.txt. These overrides touch only the
 * <title> tag (rendered with the site suffix) and the meta description.
 *
 * Titles stay at 37 characters or fewer so the suffix keeps them under 60.
 */
export const SKILL_SEO: Record<string, { title: string; description: string }> = {
  'hubspot-audit': {
    title: 'HubSpot Audit Script for Claude Code',
    description:
      'Read-only Claude Code skill that runs every HubSpot audit check by API, grades each area A-F and lists fixes. Doing it by hand? Use the audit checklist guide.',
  },
  'hubspot-implementation-plan': {
    title: 'HubSpot Cleanup Plan Generator',
    description:
      'Turns a HubSpot audit report into a phased cleanup plan with dependencies, owners and effort per task. For a blank template and example, see the guide.',
  },
  'hubspot-marketing-audit': {
    title: 'HubSpot Marketing Audit Script',
    description:
      'Claude Code skill for the marketing side of a HubSpot audit: bounces, unsubscribes, completeness, engagement and asset sprawl, graded A-F. Read-only, free.',
  },
  'hubspot-sales-audit': {
    title: 'HubSpot Sales Hub Audit Script',
    description:
      'Claude Code skill for the sales side of a HubSpot audit: pipelines, deal data, stale and past-due deals, ownership and overdue tasks, graded A-F. Read-only.',
  },
};
