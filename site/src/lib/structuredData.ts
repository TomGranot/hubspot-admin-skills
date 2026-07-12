import { SITE } from 'astrowind:config';

import type { Skill } from '~/lib/skills';
import { GITHUB_REPO_URL, extractSection, skillGithubUrl, skillPath, scriptPath } from '~/lib/skills';
import type { Problem } from '~/data/problems';

const abs = (path: string) => new URL(path, SITE.site).toString();

export const organizationSchema = () => ({
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'HubSpot Admin Skills',
  url: SITE.site,
  sameAs: [GITHUB_REPO_URL],
});

export const websiteSchema = () => ({
  '@context': 'https://schema.org',
  '@type': 'WebSite',
  name: 'HubSpot Admin Skills',
  url: SITE.site,
  description:
    '30+ open-source Claude Code skills for auditing, cleaning, enriching, segmenting, and automating HubSpot CRM.',
});

export const breadcrumbSchema = (crumbs: { name: string; path: string }[]) => ({
  '@context': 'https://schema.org',
  '@type': 'BreadcrumbList',
  itemListElement: crumbs.map((crumb, i) => ({
    '@type': 'ListItem',
    position: i + 1,
    name: crumb.name,
    item: abs(crumb.path),
  })),
});

/** Steps of the 4-stage execution pattern, as a HowTo. */
export const skillHowToSchema = (skill: Skill) => {
  const stageText = (heading: string, fallback: string) => {
    const section = extractSection(skill.body, heading);
    return section
      ? section
          .replace(/```[\s\S]*?```/g, '')
          .replace(/\s+/g, ' ')
          .trim()
          .slice(0, 300)
      : fallback;
  };

  return {
    '@context': 'https://schema.org',
    '@type': 'HowTo',
    name: skill.title,
    description: skill.description,
    totalTime: undefined,
    step: [
      {
        '@type': 'HowToStep',
        position: 1,
        name: 'Plan',
        text: stageText('Plan', 'Review the approach and provide any configuration the skill needs.'),
      },
      {
        '@type': 'HowToStep',
        position: 2,
        name: 'Before state',
        text: stageText('Before State', 'Audit the current state and export a CSV baseline of what will change.'),
      },
      {
        '@type': 'HowToStep',
        position: 3,
        name: 'Execute',
        text: stageText('Execute', 'Apply the changes via the HubSpot API or guided UI steps.'),
      },
      {
        '@type': 'HowToStep',
        position: 4,
        name: 'After state',
        text: stageText('After State', 'Verify the fix and compare before/after to confirm success.'),
      },
    ],
  };
};

export const skillArticleSchema = (skill: Skill) => ({
  '@context': 'https://schema.org',
  '@type': 'TechArticle',
  headline: skill.title,
  description: skill.description,
  url: abs(skillPath(skill.slug)),
  author: { '@type': 'Person', name: 'Tom Granot', url: 'https://consume.granot.io' },
  publisher: organizationSchema(),
  license: `${GITHUB_REPO_URL}/blob/main/LICENSE`,
  about: 'HubSpot CRM administration',
});

export const skillSourceCodeSchema = (skill: Skill) =>
  skill.scripts.length === 0
    ? undefined
    : {
        '@context': 'https://schema.org',
        '@type': 'SoftwareSourceCode',
        name: `${skill.slug} scripts`,
        description: `Ready-to-run Python scripts for the ${skill.title} skill: ${skill.scripts.join(', ')}.`,
        programmingLanguage: 'Python',
        codeRepository: skillGithubUrl(skill.slug),
        url: abs(scriptPath(skill.slug, skill.scripts[0])),
        license: `${GITHUB_REPO_URL}/blob/main/LICENSE`,
      };

export const problemFaqSchema = (problem: Problem) => ({
  '@context': 'https://schema.org',
  '@type': 'FAQPage',
  mainEntity: problem.faqs.map((faq) => ({
    '@type': 'Question',
    name: faq.question,
    acceptedAnswer: { '@type': 'Answer', text: faq.answer },
  })),
});
