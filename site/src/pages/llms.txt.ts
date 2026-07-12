import type { APIRoute } from 'astro';

import { SITE } from 'astrowind:config';

import { CATEGORIES } from '~/data/categories';
import { PROBLEMS } from '~/data/problems';
import { getSkills, GITHUB_REPO_URL, MARKETPLACE_ADD_COMMAND, PLUGIN_INSTALL_COMMAND } from '~/lib/skills';

const abs = (path: string) => new URL(path, SITE.site).toString();

export const GET: APIRoute = async () => {
  const skills = await getSkills();

  const sections = CATEGORIES.map((category) => {
    const lines = skills
      .filter((skill) => skill.category.slug === category.slug)
      .map((skill) => `- [${skill.slug}](${abs(`/skills/${skill.slug}.md`)}): ${skill.description}`);
    return `## ${category.title}\n\n${category.description}\n\n${lines.join('\n')}`;
  });

  const problemLines = PROBLEMS.map(
    (problem) => `- [${problem.title}](${abs(`/problems/${problem.slug}`)}): solved by the ${problem.skill} skill`
  );

  const body = `# HubSpot Admin Skills

> ${skills.length} open-source Claude Code skills for auditing, cleaning, enriching, segmenting, and automating HubSpot CRM. Each skill is a markdown playbook (SKILL.md) following a safe 4-stage pattern — Plan, Before (CSV baseline), Execute, After (verification) — and ${skills.filter((s) => s.scriptFiles.length > 0).length} skills include ready-to-run Python scripts (plain \`requests\` against HubSpot REST endpoints, PEP 723 inline metadata, run via \`uv run\`).

Install in Claude Code:

\`\`\`
${MARKETPLACE_ADD_COMMAND}
${PLUGIN_INSTALL_COMMAND}
\`\`\`

Requirements: a HubSpot private app token (HUBSPOT_ACCESS_TOKEN in .env), Python 3.10+ with uv for scripted skills.

Machine-readable catalog: ${abs('/api/skills.json')}
All skills in one fetch: ${abs('/llms-full.txt')}
Raw scripts: ${abs('/skills/<slug>/scripts/<file>.py')} (before/execute/after stages plus any nested helpers; full list per skill in skills.json)
Source repository: ${GITHUB_REPO_URL}

${sections.join('\n\n')}

## Common problems mapped to skills

${problemLines.join('\n')}

## Optional

- [Install guide](${abs('/install')}): human and agent installation instructions
- [Contributing](${abs('/contributing')}): how new skills are contributed, including automatically via the audit skill
`;

  return new Response(body, { headers: { 'Content-Type': 'text/markdown; charset=utf-8' } });
};
