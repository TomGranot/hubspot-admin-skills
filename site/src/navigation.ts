import { getPermalink } from './utils/permalinks';

import { CATEGORIES } from '~/data/categories';
import { GITHUB_REPO_URL } from '~/lib/skills';

export const headerData = {
  links: [
    {
      text: 'Skills',
      href: getPermalink('/skills'),
    },
    {
      text: 'Categories',
      links: CATEGORIES.map((category) => ({
        text: category.title,
        href: getPermalink(`/categories/${category.slug}`),
      })),
    },
    {
      text: 'Problems',
      href: getPermalink('/problems'),
    },
    {
      text: 'For Agents',
      href: getPermalink('/install#agents'),
    },
    {
      text: 'Contributing',
      href: getPermalink('/contributing'),
    },
  ],
  actions: [
    { text: 'Install', href: getPermalink('/install'), variant: 'primary' },
    { text: 'GitHub', href: GITHUB_REPO_URL, target: '_blank', icon: 'tabler:brand-github' },
  ],
};

export const footerData = {
  links: [
    {
      title: 'Skills',
      links: [
        { text: 'All skills', href: getPermalink('/skills') },
        ...CATEGORIES.map((category) => ({
          text: category.title,
          href: getPermalink(`/categories/${category.slug}`),
        })),
      ],
    },
    {
      title: 'Solve a problem',
      links: [
        { text: 'Common HubSpot problems', href: getPermalink('/problems') },
        { text: 'Run a portal audit', href: getPermalink('/skills/hubspot-audit') },
        { text: 'Get a cleanup plan', href: getPermalink('/skills/hubspot-implementation-plan') },
        { text: 'Weekly maintenance', href: getPermalink('/skills/weekly-cleanup-routine') },
      ],
    },
    {
      title: 'For agents',
      links: [
        { text: 'llms.txt', href: '/llms.txt' },
        { text: 'llms-full.txt', href: '/llms-full.txt' },
        { text: 'skills.json', href: '/api/skills.json' },
        { text: 'Agent install guide', href: getPermalink('/install#agents') },
      ],
    },
    {
      title: 'Project',
      links: [
        { text: 'Install', href: getPermalink('/install') },
        { text: 'Contributing', href: getPermalink('/contributing') },
        { text: 'GitHub', href: GITHUB_REPO_URL },
        { text: 'MIT License', href: `${GITHUB_REPO_URL}/blob/main/LICENSE` },
      ],
    },
  ],
  secondaryLinks: [],
  socialLinks: [{ ariaLabel: 'Github', icon: 'tabler:brand-github', href: GITHUB_REPO_URL }],
  footNote: `
    Built by <a class="text-blue-600 underline dark:text-muted" href="https://consume.granot.io">Tom Granot</a> · Open source under MIT · Not affiliated with HubSpot, Inc.
  `,
};
