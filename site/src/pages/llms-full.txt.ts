import type { APIRoute } from 'astro';

import { SITE } from 'astrowind:config';

import { getSkills, GITHUB_REPO_URL } from '~/lib/skills';

// Every SKILL.md concatenated, for single-fetch ingestion by agents.
export const GET: APIRoute = async () => {
  const skills = await getSkills();

  const header = `# HubSpot Admin Skills — full skill documentation

> All ${skills.length} skills, concatenated. Index: ${new URL('/llms.txt', SITE.site)}
> Source: ${GITHUB_REPO_URL}

`;

  const body = skills
    .map(
      (skill) =>
        `\n\n---\n\n<!-- skill: ${skill.slug} | category: ${skill.category.slug} | scripts: ${
          skill.scripts.join(',') || 'none'
        } -->\n\n${skill.raw.trim()}`
    )
    .join('');

  return new Response(header + body, { headers: { 'Content-Type': 'text/markdown; charset=utf-8' } });
};
