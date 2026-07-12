import type { APIRoute } from 'astro';

import { SITE } from 'astrowind:config';

import { getProblemsForSkill } from '~/data/problems';
import {
  getSkills,
  skillGithubUrl,
  GITHUB_REPO_URL,
  MARKETPLACE_ADD_COMMAND,
  PLUGIN_INSTALL_COMMAND,
} from '~/lib/skills';

const abs = (path: string) => new URL(path, SITE.site).toString();

// Machine-readable skill catalog for agents.
export const GET: APIRoute = async () => {
  const skills = await getSkills();

  const manifest = {
    name: 'hubspot-admin-skills',
    description:
      'Open-source Claude Code skills for auditing, cleaning, enriching, segmenting, and automating HubSpot CRM.',
    repository: GITHUB_REPO_URL,
    license: 'MIT',
    install: {
      marketplace_add: MARKETPLACE_ADD_COMMAND,
      plugin_install: PLUGIN_INSTALL_COMMAND,
    },
    requirements: {
      hubspot: 'Private app token (HUBSPOT_API_TOKEN) with CRM scopes; Marketing Professional+ for workflow skills',
      python: 'Python 3.10+ with uv, for scripted skills',
    },
    endpoints: {
      llms_txt: abs('/llms.txt'),
      llms_full_txt: abs('/llms-full.txt'),
      skill_markdown: abs('/skills/{slug}.md'),
      skill_script: abs('/skills/{slug}/scripts/{stage}.py'),
    },
    count: skills.length,
    skills: skills.map((skill) => ({
      slug: skill.slug,
      name: skill.title,
      command: `/${skill.slug}`,
      description: skill.description,
      category: skill.category.slug,
      version: skill.version,
      license: skill.license,
      scripted: skill.scripts.length > 0,
      scripts: skill.scripts.map((stage) => ({ stage, url: abs(`/skills/${skill.slug}/scripts/${stage}.py`) })),
      urls: {
        html: abs(`/skills/${skill.slug}`),
        markdown: abs(`/skills/${skill.slug}.md`),
        github: skillGithubUrl(skill.slug),
      },
      solves: getProblemsForSkill(skill.slug).map((problem) => ({
        title: problem.title,
        url: abs(`/problems/${problem.slug}`),
      })),
    })),
  };

  return new Response(JSON.stringify(manifest, null, 2), {
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
};
